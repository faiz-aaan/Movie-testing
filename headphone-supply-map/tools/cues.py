"""voice/cues.json: where each narration line starts on the film clock + the exact subtitle text.
Durations come from voice/dur.json (written by core/tts/tts.py). Run after regenerating the voice."""
import json, os, sys
P = sys.argv[1]
dur = json.load(open(os.path.join(P, 'voice', 'dur.json')))
lines = {l['id']: l['text'] for l in json.load(open(os.path.join(P, 'voice', 'lines.json')))}
START = {'l1': 0.8, 'l2': 4.6, 'l3': 10.0, 'l4': 15.6, 'l5': 22.0, 'l6': 27.6}
SUB = {  # subtitles: digits as digits, one line each
    'l1': 'Headphones look simple. The map behind them is not.',
    'l2': 'Magnets like the ones in its drivers? More than 9 in 10 are made in China.',
    'l3': 'Lithium for the battery is mostly refined in China too: about 7 in 10.',
    'l4': "And one Taiwan-based foundry takes about 7 in 10 of the world's contract chip sales.",
    'l5': 'It all converges on electronics clusters in southern China.',
    'l6': 'Then it ships to everyone who presses play.'}
cues = [{'id': k, 't0': t, 't1': round(t + dur[k] + .15, 3), 'text': SUB[k], 'say': lines[k]} for k, t in START.items()]
json.dump(cues, open(os.path.join(P, 'voice', 'cues.json'), 'w'), indent=1)
for c in cues: print(c['id'], c['t0'], c['t1'])
