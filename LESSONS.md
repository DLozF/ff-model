# Lessons

- Yahoo settings reuse labels such as `Sack` across team defense and IDP sections. Parse scoring rows with section context; a flat label dictionary silently applies the wrong value.
- Yahoo playoff text may include an end-date day number after the week list. Parse only the text after `Week` and before any parenthetical date.
- Long P8 runs can exceed the foreground tool timeout even when the script is healthy. Run them as tracked background processes with durable log redirection, then verify both exit status and reports.
- Custom league scoring invalidates `pts_ppr` as both the projection target and actual score. Preserve full projected stat lines, rescore them without unprojectable bonuses, and derive historical bonus counts from play-by-play.
