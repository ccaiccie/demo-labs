# Facilitator build and optional source reveal

If doing this as a blind exercise, stop here and let someone else build the original. The analyst should receive only the resulting `tip-original.elf`, never this directory.

On a 64-bit Ubuntu desktop, with GCC or another C compiler, binutils (`strip`), pkg-config, and the GTK 3 development library installed (`build-essential pkg-config libgtk-3-dev` on Ubuntu):

```sh
cd original-source-reveal
mkdir -p build
cc -std=c11 -O0 -g0 -Wall -Wextra tip.c -o build/tip-original.elf $(pkg-config --libs gtk+-3.0)
strip --strip-all build/tip-original.elf
file build/tip-original.elf
sha256sum build/tip-original.elf
```

Copy only the resulting ELF to the analyst's working folder. Send the hash separately so the analyst can verify the exact same bytes. Rebuilds can have different hashes and function addresses. The GTK 3 runtime must be available on the analyst's graphical Linux machine.

After comparing the two GUIs, inspect [tip.c](tip.c) as a reveal. Try accounting for any behavior not covered by the visible test matrix.
