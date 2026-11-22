# Evidence notes (spoilers)

- **Scope:** The recorded reference was a stripped x86-64 ELF with SHA-256 `c3ad2175561d0c5cf921ae0dc03e0bd4c5d1afd4b74d2010490358702f7df6b0`. A local rebuild can differ. The reference analysis used Ghidra 12.2 and REA 6.10.1.
- **Observed at runtime:** The GTK window accepted two inputs and updated the same status line on a button click or Enter. The six cases in the behavior spec include normal output, zero, an exact half-cent, two rejection paths, and recovery after editing.
- **Native Ghidra:** In the reference import, the callback at `0x0010172b` reads both entries and updates the label. The arithmetic helper at `0x00101518` decompiled to an integer expression of the form `(param_2 * param_1 + 0x32) / 100`. In context the inputs are whole percent and bill cents; `0x32` is 50 decimal. The bill is validated before percent, and the rounded tip is added to the bill.
- **REA MCP cross-check:** A read-only query against a separate import of the same executable reported the same helper and event-to-output flow. This is a summary of the response, not a verbatim log. It does not establish that REA produced the Swing program.
- **Independent check:** The separate builder used the behavior spec, without consulting the original code or executable. The Swing button/Enter tests assert visible results, error replacement, preserved inputs, precedence, and field-length limits. On five cents at ten percent, `(5 * 10 + 50) / 100` is 1 cent with integer division; the resulting total is 6 cents.

Don't treat function addresses, decompiler parameter names, appearance, or untested parsing spellings as universal.
