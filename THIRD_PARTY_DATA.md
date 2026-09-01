# Third-party vocabulary and pronunciation data

## JMdict

The generated Japanese vocabulary in `public/data/db.json` uses headwords,
readings, parts of speech, and English glosses from the JMdict
Japanese-Multilingual Dictionary maintained by the Electronic Dictionary
Research and Development Group (EDRDG).

- Project: https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project
- Licence statement: https://www.edrdg.org/edrdg/licence.html
- Licence: Creative Commons Attribution-ShareAlike 4.0

The derived vocabulary data remains subject to CC BY-SA 4.0. JMdict requires
applications incorporating its data to provide attribution and a regular data
update procedure. `scripts/import_jmdict.py --refresh --write` is the refresh
path for this project.

## UniDic Lite

Pitch-accent types are obtained with UniDic Lite 2.1.2 through fugashi. The
accent types are transformed into the app's stylized three-level contours.

- UniDic: https://clrd.ninjal.ac.jp/unidic/en/
- UniDic Lite: https://github.com/polm/unidic-lite
- UniDic 2.1.2 licence used here: New BSD
- fugashi licence: MIT; bundled MeCab components use the BSD licence

Automatically generated contours are search aids, not a claim of authoritative
pronunciation for every context or dialect.
