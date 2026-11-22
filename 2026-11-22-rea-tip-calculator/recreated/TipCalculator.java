import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.EventQueue;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.math.BigDecimal;
import java.util.Locale;
import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JTextField;
import javax.swing.UIManager;
import javax.swing.WindowConstants;
import javax.swing.text.AbstractDocument;
import javax.swing.text.AttributeSet;
import javax.swing.text.BadLocationException;
import javax.swing.text.DocumentFilter;

/** Standalone Swing implementation of a tip calculator. */
public final class TipCalculator {
    private static final String BILL_ERROR =
            "Enter a bill from 0 to 10000.00 (up to 2 decimals).";
    private static final String PERCENT_ERROR =
            "Enter a whole tip percentage from 0 to 100.";
    static final String INITIAL_OUTCOME = "Tip and total will appear here.";
    final JTextField bill = new HintField("e.g. 42.50");
    final JTextField percentage = new HintField("e.g. 18");
    final JLabel outcome = new JLabel(INITIAL_OUTCOME);
    final JButton calculate = new JButton("Calculate");

    TipCalculator() {
        calculate.addActionListener(event -> calculate());
        bill.addActionListener(event -> calculate.doClick(0));
        percentage.addActionListener(event -> calculate.doClick(0));
    }

    private void createWindow() {
        JFrame frame = new JFrame("Tip Calculator");
        frame.setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);

        JLabel title = new JLabel("Tip Calculator");
        title.setFont(title.getFont().deriveFont(Font.BOLD, 20f));

        JPanel controls = new JPanel(new GridBagLayout());
        controls.setBorder(BorderFactory.createEmptyBorder(10, 0, 10, 0));
        addField(controls, 0, "Bill amount (USD)", bill);
        addField(controls, 2, "Tip percentage", percentage);

        GridBagConstraints buttonPosition = new GridBagConstraints();
        buttonPosition.gridx = 0;
        buttonPosition.gridy = 4;
        buttonPosition.weightx = 1;
        buttonPosition.fill = GridBagConstraints.HORIZONTAL;
        buttonPosition.insets = new Insets(10, 0, 0, 0);
        controls.add(calculate, buttonPosition);

        JPanel main = new JPanel(new BorderLayout());
        main.setBorder(BorderFactory.createEmptyBorder(16, 18, 16, 18));
        main.add(title, BorderLayout.NORTH);
        main.add(controls, BorderLayout.CENTER);
        main.add(outcome, BorderLayout.SOUTH);
        frame.setContentPane(main);
        frame.getRootPane().setDefaultButton(calculate);
        // Leave enough room for either error, even before it has been displayed.
        JLabel representative = new JLabel(BILL_ERROR);
        outcome.setPreferredSize(representative.getPreferredSize());
        frame.pack();
        frame.setMinimumSize(frame.getSize());
        frame.setLocationByPlatform(true);
        frame.setVisible(true);
        bill.requestFocusInWindow();
    }

    private static void addField(JPanel panel, int row, String title, JTextField field) {
        JLabel label = new JLabel(title);
        label.setLabelFor(field);

        GridBagConstraints position = new GridBagConstraints();
        position.gridx = 0;
        position.gridy = row;
        position.weightx = 1;
        position.anchor = GridBagConstraints.LINE_START;
        position.fill = GridBagConstraints.HORIZONTAL;
        position.insets = new Insets(5, 0, 3, 0);
        panel.add(label, position);

        position.gridy = row + 1;
        position.insets = new Insets(0, 0, 4, 0);
        panel.add(field, position);
    }

    private void calculate() {
        String billText = bill.getText();
        String percentText = percentage.getText();

        // Validate syntax before converting, so no fraction of a cent is lost.
        if (!billText.matches("[0-9]+(?:\\.[0-9]{1,2})?")) {
            outcome.setText(BILL_ERROR);
            return;
        }
        BigDecimal amount = new BigDecimal(billText);
        if (amount.compareTo(BigDecimal.valueOf(10_000)) > 0) {
            outcome.setText(BILL_ERROR);
            return;
        }
        if (!percentText.matches("[0-9]+")) {
            outcome.setText(PERCENT_ERROR);
            return;
        }
        int rate;
        try {
            rate = Integer.parseInt(percentText);
        } catch (NumberFormatException exception) {
            outcome.setText(PERCENT_ERROR);
            return;
        }
        if (rate > 100) {
            outcome.setText(PERCENT_ERROR);
            return;
        }

        long billCents = amount.movePointRight(2).longValueExact();
        // Add half of the divisor before dividing nonnegative integers (half-up).
        long tipCents = (billCents * rate + 50) / 100;
        outcome.setText("Tip: " + dollars(tipCents) + "    Total: " + dollars(billCents + tipCents));
    }

    private static String dollars(long cents) {
        return String.format(Locale.ROOT, "$%d.%02d", cents / 100, cents % 100);
    }

    /** A drawn hint never becomes part of the actual field value. */
    private static final class HintField extends JTextField {
        private final String hint;

        HintField(String hint) {
            super(20);
            this.hint = hint;
            getAccessibleContext().setAccessibleDescription(hint);
            ((AbstractDocument) getDocument()).setDocumentFilter(new InputLengthLimit());
            addFocusListener(new java.awt.event.FocusAdapter() {
                @Override
                public void focusGained(java.awt.event.FocusEvent event) {
                    repaint();
                }

                @Override
                public void focusLost(java.awt.event.FocusEvent event) {
                    repaint();
                }
            });
        }

        @Override
        protected void paintComponent(Graphics graphics) {
            super.paintComponent(graphics);
            if (hasFocus() || !getText().isEmpty()) {
                return;
            }
            Graphics overlay = graphics.create();
            try {
                Color disabled = UIManager.getColor("TextField.inactiveForeground");
                overlay.setColor(disabled != null ? disabled : Color.GRAY);
                overlay.setFont(getFont());
                Insets insets = getInsets();
                int baseline = getBaseline(getWidth(), getHeight());
                if (baseline >= 0) {
                    overlay.drawString(hint, insets.left + 2, baseline);
                }
            } finally {
                overlay.dispose();
            }
        }
    }

    /** Limit typed or pasted input to 32 characters, preserving the existing text. */
    private static final class InputLengthLimit extends DocumentFilter {
        private static final int MAX_LENGTH = 32;

        @Override
        public void insertString(FilterBypass bypass, int offset, String text, AttributeSet attributes)
                throws BadLocationException {
            replace(bypass, offset, 0, text, attributes);
        }

        @Override
        public void replace(FilterBypass bypass, int offset, int length,
                            String text, AttributeSet attributes) throws BadLocationException {
            if (text == null) {
                bypass.replace(offset, length, null, attributes);
                return;
            }
            String existing = bypass.getDocument().getText(0, bypass.getDocument().getLength());
            int unchanged = existing.codePointCount(0, offset)
                          + existing.codePointCount(offset + length, existing.length());
            int remaining = MAX_LENGTH - unchanged;
            int accepted = text.codePointCount(0, text.length());
            if (remaining > 0 || text.isEmpty()) {
                int end = text.offsetByCodePoints(0, Math.min(remaining, accepted));
                bypass.replace(offset, length, text.substring(0, end), attributes);
            }
        }
    }

    public static void main(String[] args) {
        EventQueue.invokeLater(() -> new TipCalculator().createWindow());
    }
}
