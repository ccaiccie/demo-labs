import java.awt.EventQueue;

/** Dependency-free checks of the Swing button action and its visible status. */
public final class TipCalculatorTest {
    private static void assertEquals(String name, String expected, String actual) {
        if (!expected.equals(actual)) {
            throw new AssertionError(name + ": expected [" + expected + "] but got [" + actual + "]");
        }
    }

    private static void submit(TipCalculator app, String bill, String percentage, String expected) {
        app.bill.setText(bill);
        app.percentage.setText(percentage);
        app.calculate.doClick(0);
        assertEquals("input " + bill + " / " + percentage, expected, app.outcome.getText());
    }

    public static void main(String[] args) throws Exception {
        EventQueue.invokeAndWait(() -> {
            TipCalculator app = new TipCalculator();
            assertEquals("initial bill", "", app.bill.getText());
            assertEquals("initial percentage", "", app.percentage.getText());
            assertEquals("initial status", "Tip and total will appear here.", app.outcome.getText());
            submit(app, "42.50", "18", "Tip: $7.65    Total: $50.15");
            submit(app, "0.05", "10", "Tip: $0.01    Total: $0.06");
            submit(app, "0", "0", "Tip: $0.00    Total: $0.00");
            submit(app, "10.001", "10", "Enter a bill from 0 to 10000.00 (up to 2 decimals).");
            assertEquals("bill remains after error", "10.001", app.bill.getText());
            assertEquals("percentage remains after error", "10", app.percentage.getText());
            submit(app, "20.00", "101", "Enter a whole tip percentage from 0 to 100.");
            assertEquals("bill remains after bad percentage", "20.00", app.bill.getText());
            assertEquals("bad percentage remains", "101", app.percentage.getText());
            app.percentage.setText("15");
            app.percentage.postActionEvent();
            assertEquals("Enter recalculates", "Tip: $3.00    Total: $23.00", app.outcome.getText());
            assertEquals("bill remains after Enter", "20.00", app.bill.getText());
            assertEquals("new percentage remains after Enter", "15", app.percentage.getText());
            submit(app, "10.00", "10.5", "Enter a whole tip percentage from 0 to 100.");
            submit(app, "0.04", "10", "Tip: $0.00    Total: $0.04");
            submit(app, "10000.00", "100", "Tip: $10000.00    Total: $20000.00");
            submit(app, "10000.01", "100", "Enter a bill from 0 to 10000.00 (up to 2 decimals).");
            app.bill.setText("1.00");
            app.bill.postActionEvent();
            assertEquals("Enter in bill recalculates", "Tip: $1.00    Total: $2.00", app.outcome.getText());

            submit(app, "10.001", "101", "Enter a bill from 0 to 10000.00 (up to 2 decimals).");
            String maximum = "01234567890123456789012345678901";
            app.bill.setText(maximum + "2345");
            app.percentage.setText(maximum + "6789");
            assertEquals("bill length cap", maximum, app.bill.getText());
            assertEquals("percentage length cap", maximum, app.percentage.getText());
        });
        System.out.println("Swing behavior checks passed.");
    }
}
