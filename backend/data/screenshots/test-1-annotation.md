# test-1.jfif — Ground Truth Annotation

## Screenshot details
- File: `test-1.jfif` (1024×576, JPEG/JFIF)
- Game language: Spanish
- Screen type: hand (playing a round)

## Jokers (left → right)
| Slot | Name | Edition | Notes |
|------|------|---------|-------|
| 0 | Square Joker | Foil | Foil edition overlay obscures visual features |
| 1 | Scholar | Base | Not hovered; no description visible |
| 2 | Mime | Base | Not hovered; no description visible |
| 3 | Yorick | Base | Hovered — description "YORICK" visible in crop |
| 4 | Yorick | Base | Hovered — detected as tarot by YOLO, description "YORICK" visible |

## Resources
| Field | Value |
|-------|-------|
| Money | $82 |
| Hands remaining | 4 |
| Discards remaining | 0 |

## Blind / Progress
| Field | Value |
|-------|-------|
| Ante | 10 |
| Round | 27 |
| Target score (Big Blind) | 1,650,000 |

## Cards in hand (partial — YOLO only detected 2 of the hand)
- A♥ (Ace of Hearts)
- A (Ace, suit undetected)

## Known CV pipeline issues for this screenshot
1. **Square Joker (foil)**: Foil edition adds a colour overlay that shifts the
   spatial colour histogram away from the reference sprite, causing the classifier
   to score below the confidence threshold. Result: `Joker 1 (unidentified)`.
2. **Scholar / Mime**: Not hovered, so no description-panel text is visible in
   their crops. The visual classifier (wiki sprites vs JPEG screenshot crops) does
   not reliably distinguish these from other jokers. Result: `Joker N (unidentified)`.
3. **Second Yorick (tarot misclassification)**: YOLO labels the hovered Yorick as
   `tarot_card` because the open description panel resembles a tarot card layout.
   The extractor now detects this via OCR and redirects it to the joker list.
4. **Hand cards**: Only 2 of the hand cards were detected. The remaining cards
   overlap with the deck pile / other UI and were missed by the detector.
