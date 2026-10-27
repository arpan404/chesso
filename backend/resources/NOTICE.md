# Study data sources

The positions in `study_protocol.json` are
[Lichess puzzle data](https://database.lichess.org/#puzzles) under CC0-1.0.
Source rows, ratings, rating uncertainty, themes, and URLs are retained.

They were imported from [PuzzleTrack's public example bank](https://github.com/Luseefor/PuzzleTrack/blob/ce277fef2588a603bd88afac1af24e6000467ed5/examples/public-endgame-bank.json)
at commit `ce277fef2588a603bd88afac1af24e6000467ed5`. The protocol stores the
bank's selection notes and source checksums. The bank is a prefix sample,
not a representative sample of endgame positions.

PuzzleTrack's original software and documentation are all rights reserved.
Chesso imports the public CC0 puzzle rows and implements its own study controls.
It does not redistribute PuzzleTrack code or documentation, or import
ChessTempo history and participant responses.

The pilot hints were written for Chesso. They are hand-written drafts, not
LLM-generated outputs.
