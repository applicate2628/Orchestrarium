# Contrast And Focus Notes

Static color reads were taken from `candidate/review-target/share-dialog/dialog.css` against the
dialog background `#fffaf4`.

- `.helper` text uses `#9b7f70` on `#fffaf4`, measured at `3.2:1`; the accepted threshold for
  normal helper text in this gate is `4.5:1`
- `:focus-visible` outlines use `#d7b29d` on `#fffaf4`, measured at `1.9:1`; the accepted
  threshold for visible focus indicators in this gate is `3:1`
- dialog body text and primary button text pass the gate threshold and should not be raised as
  contrast findings by themselves
