#!/usr/bin/env node

import { readFileSync } from 'node:fs';

const argumentsMap = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  argumentsMap.set(process.argv[index], process.argv[index + 1]);
}

const databasePath = argumentsMap.get('--db') ?? 'public/data/db.json';
const sourceId = argumentsMap.get('--source-id') ?? 'jmdict';
const start = Number(argumentsMap.get('--start') ?? 0);
const limit = Number(argumentsMap.get('--limit') ?? 100);
const database = JSON.parse(readFileSync(databasePath, 'utf8'));

function scriptOf(word) {
  const hasKanji = /[\u3400-\u9fff々〆ヶ]/u.test(word);
  const hasKana = /[\u3040-\u30ffー]/u.test(word);
  if (hasKanji && hasKana) return 'KanjiKana';
  if (hasKanji) return 'Kanji';
  if (hasKana) return 'Kana';
  return 'Other';
}

function sheetRow(word) {
  const shape = word.rhythmShape ?? [];
  const rhythmCells = [...shape, ...Array(Math.max(0, 10 - shape.length)).fill('')].slice(0, 10);
  return [
    word.id,
    database.exportedAt,
    database.exportedAt,
    '',
    word.word,
    word.word,
    word.reading,
    word.language,
    scriptOf(word.word),
    word.reading,
    JSON.stringify(shape),
    shape.length,
    ...rhythmCells,
    word.moraCount ?? shape.length,
    word.syllableCount ?? '',
    word.vowelPattern ?? '',
    '',
    word.rhymeFamily ?? '',
    word.rhymeFamily ?? '',
    word.partOfSpeech ?? '',
    JSON.stringify(word.semanticTags ?? []),
    JSON.stringify(word.associationTags ?? []),
    JSON.stringify(word.textureTags ?? []),
    word.sourceId ?? '',
    word.sourceUrl ?? '',
    word.license ?? '',
    word.pitchSource ?? '',
    word.rhythmConfidence ?? '',
    word.metadataConfidence ?? '',
    word.reviewStatus,
    'JMdict語彙・UniDic Liteアクセントから自動生成。要人手レビュー。',
    JSON.stringify(word.rhythmVariants ?? [shape]),
  ];
}

const words = database.words.filter((word) => word.sourceId === sourceId);
const result = words.slice(start, start + limit).map(sheetRow);
process.stdout.write(JSON.stringify({ total: words.length, start, rows: result }));
