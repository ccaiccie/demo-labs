# Can REA help recreate a desktop app?

Use a tiny desktop tip calculator to practice separating visible behavior, analysis evidence, and implementation. The original app is GTK/C; the recreation is Java Swing. Both run locally and neither performs payments.

**Before starting:** If you want a blind exercise, ask someone else to build the original using the [facilitator instructions](original-source-reveal/README.md). Only the stripped executable should enter the analyst's working folder. The facilitator shares the expected SHA-256 separately. This repository contains source, not executables.

## 1. Observe the original

In the analyst folder on a graphical 64-bit Ubuntu/Linux system with GTK 3:

```sh
file tip-original.elf
sha256sum tip-original.elf
chmod u+x tip-original.elf
./tip-original.elf
```

Compare the hash with the facilitator's. Enter a bill of `42.50` and a tip percentage of `18`. Click **Calculate** and write down the actual output. Then try the acceptance cases below. Don't open the source reveal or recreation yet.

## 2. Trace the calculation in Ghidra and REA

1. In Ghidra, create a non-shared project, import just the executable, open it in CodeBrowser, and run auto-analysis. Check that Ghidra recognized the ELF and the correct architecture.
2. Search for the `Calculate` string and follow its references. In Listing and Decompile, find the nearby signal hookup. Follow the callback from the button and input fields into validation, rounding, and the label update.
3. With your REA MCP server already configured, ask your MCP client for read-only evidence from its Ghidra import of the same ELF. Example: “Identify the project/program and the GUI callback. Show the actual arithmetic helper's decompiled expression and explain its rounding on five cents at ten percent.” Compare the service response to native Ghidra. A connection or tool listing alone does not establish the arithmetic.
4. Write a behavior-only brief for a separate builder. Keep the executable, source, and decompiler view out of that handoff. Compare your notes with the [observed behavior spec](TIP-BEHAVIOR-SPEC.md) and [recorded evidence](EVIDENCE.md) after the exercise.

## 3. Build and compare the independent Swing recreation

From the lab folder, in a second terminal with a JDK (Java 21 or later) and a graphical desktop:

```sh
cd recreated
mkdir -p build
javac -d build TipCalculator.java TipCalculatorTest.java
java -Djava.awt.headless=true -cp build TipCalculatorTest
java -cp build TipCalculator
```

Run both GUIs side by side. Submit the same sequence in each:

| Bill | Tip percentage | Expected outcome |
| --- | --- | --- |
| 42.50 | 18 | Tip $7.65; total $50.15 |
| 0.05 | 10 | Tip $0.01; total $0.06 |
| 0 | 0 | Tip $0.00; total $0.00 |
| 10.001 | 0 | Bill validation message; inputs stay |
| 20.00 | 101 | Percentage validation message; inputs stay |
| 20.00 | Change 101 to 15; press Enter | Tip $3.00; total $23.00 |

These checks cover behavior, not every parser edge case or the exact look of the app. To finish, open the optional [original C source](original-source-reveal/tip.c) and explain what the analysis recovered and what it did not.
