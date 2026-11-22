# Tip Calculator — behavior observed from the original artifact

Source was not provided to the analyst. This specification is from observed GTK operation and Ghidra's static evidence for the stripped x86-64 ELF identified by SHA-256 `c3ad2175561d0c5cf921ae0dc03e0bd4c5d1afd4b74d2010490358702f7df6b0`.

## User interface

- A single desktop window titled “Tip Calculator” with a simple vertical stack, heading “Tip Calculator”, labels “Bill amount (USD)” and “Tip percentage”, text inputs, a full-width Calculate button, and status output. GTK requests 460 × 280 content and uses 24-pixel margins and 12-pixel vertical spacing as desktop reference; system decoration and minimum constraints may expand it.
- Inputs begin empty with placeholders “e.g. 42.50” and “e.g. 18”; focus starts in the first entry and both are configured for 32 characters max.
- Initially the status reads “Tip and total will appear here.”
- Calculate click or Enter from either input runs the same operation. Results and errors replace the single status, retaining the entered values.

## Calculation and validation

1. Check the bill first. Accept amounts in the inclusive range 0–10000.00, up to two decimal places. Invalid result: “Enter a bill from 0 to 10000.00 (up to 2 decimals).”
2. Check the tip percentage as a whole number, inclusive range 0–100. Invalid result: “Enter a whole tip percentage from 0 to 100.”
3. Use nonnegative integer cents. Multiply bill cents by the whole percent, add 50, then divide by 100 with truncating integer division to produce rounded tip cents. Add that to original bill cents for total.
4. Show both dollar amounts with two fractional digits: `Tip: $7.65    Total: $50.15`.

## Observed GUI acceptance cases

| Bill | Percent | Observed result |
|---|---:|---|
| 42.50 | 18 | Tip: $7.65; Total: $50.15 |
| 0.05 | 10 | Tip: $0.01; Total: $0.06 |
| 0 | 0 | Tip: $0.00; Total: $0.00 |
| 10.001 | 0 | Bill validation message |
| 20.00 | 101 | Tip percentage validation message |
| 20.00 | 15 entered after invalid 101, then Enter | Tip: $3.00; Total: $23.00 |

The recreation should be a new implementation of this behavior, not a copy of the original binary or source. Unobserved parsing spellings (e.g. leading whitespace or plus sign) are not specified here.
