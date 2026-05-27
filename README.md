# YALLA PIPS Trading Keyboard — Standalone Software
### No StreamDock app required ✔

## Install (End User)
1. Copy `YallaPips_Keyboard.exe` and `config.json` to any folder
2. Run `YallaPips_Keyboard.exe`  — appears in system tray (bottom-right)
3. MT5 must be running for trade keys to work
4. Right-click tray icon → **Settings** to configure symbol, lots, SL/TP etc.

## Build EXE (Developer)
```bash
pip install -r requirements.txt
pyinstaller main.spec
# Output: dist/YallaPips_Keyboard.exe
```

## Key Layout (left→right, top→bottom)
| Key | Action |
|-----|--------|
| 1  | BUY — opens buy market order |
| 2  | SELL — opens sell market order |
| 3  | CLOSE ALL — closes every position |
| 4  | CLOSE LOSING — closes only losing positions |
| 5  | CLOSE PROFIT — closes only profitable positions |
| 6  | SL → BE — moves all SL to entry |
| 7  | CLOSE 25% — partial close quarter |
| 8  | CLOSE 50% — partial close half |
| 9  | CLOSE 75% — partial close three-quarters |
| 10 | AUTO BE 20 — toggle (background monitor, moves SL at 20 pips) |
| 11 | PARTIAL SL — tightens SL 50% towards entry |
| 12 | SL TRAILING — toggle (background trailing, 1s interval) |
| 13 | TRADINGVIEW — opens TradingView.com in browser |
| 14 | FOREXFACTORY — opens ForexFactory.com in browser |
| 15 | MT5 — live balance/equity/P&L on key, tap to refresh |

## Device Compatibility
Auto-detects StreamDock and Elgato Stream Deck 15-key devices.
If your device isn't found, enter its VID/PID in Settings (use hex, e.g. 0fd9).

## Files
- `YallaPips_Keyboard.exe` — main app
- `config.json` — all settings (edit manually or via Settings window)
- `yallapips.log` — debug log
