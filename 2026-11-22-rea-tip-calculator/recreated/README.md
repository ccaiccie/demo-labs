# Tip Calculator: Independent Swing Recreation

This small desktop application is a behavior-based teaching example. It uses only the Java standard library and does not require Gradle, Maven, external libraries, or network access.

## Build and open the window

From this directory, in a graphical session with a JDK installed:

```sh
mkdir -p build
javac -d build TipCalculator.java
java -cp build TipCalculator
```

Enter a bill and a tip percentage and click **Calculate**. Pressing Enter also activates the button.

## Run the behavior checks

The test runs the Swing Calculate button action without opening a window:

```sh
javac -d build TipCalculator.java TipCalculatorTest.java
java -Djava.awt.headless=true -cp build TipCalculatorTest
```

## Behavior covered

The recreation was built from a behavior specification, not from the original source or binary. The reported live cases test an ordinary calculation, exact half-cent rounding, zero, an over-precision bill, and correcting an invalid percentage with Enter. Additional synthetic checks cover the inclusive upper limits, a fractional percentage, and rounding below half a cent. These are tests of this implementation, not claims about unobserved behavior in the original. The window uses Swing's own appearance; it is not a pixel copy.

Both fields cap input at 32 characters; hints appear only in an empty, unfocused field. Calculate and Enter in either field use the same action.

The analyzed calculation matches this Swing implementation: validate the bill before the percentage; compute tip cents as `(billCents * wholePercent + 50) / 100` with integer division; add tip cents to bill cents for the total. Adding 50 before dividing by 100 rounds exact half-cents up.

Untested lexical choices: the recreated bill requires ASCII digits before an optional period, with one or two digits after a period. The percentage accepts ASCII digits only. These forms accept leading zeroes, but not whitespace, signs, commas, scientific notation, a leading period, or a trailing period. Do not assume matching parser behavior in the original for those forms. The source and tests are UTF-8 and use only the JDK.
