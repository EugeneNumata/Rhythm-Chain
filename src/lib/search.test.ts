import { describe, expect, it } from 'vitest';
import generatedDatabase from '../../public/data/db.json';
import type { WordDatabase, WordEntry } from '../types';
import { associationSimilarity, rankWords, rhythmSimilarity } from './search';

const sharishari: WordEntry = {
  id: 'a',
  word: 'シャリシャリ',
  reading: 'しゃりしゃり',
  language: 'ja',
  rhythmShape: [1, 2, 1, 2],
  vowelPattern: 'ai-ai',
  rhymeFamily: '-ari',
  semanticTags: ['食感'],
  associationTags: ['氷'],
  textureTags: ['硬い'],
  reviewStatus: 'draft',
};

const ice: WordEntry = {
  id: 'b',
  word: '氷',
  reading: 'こおり',
  language: 'ja',
  rhythmShape: [],
  vowelPattern: 'ooi',
  rhymeFamily: '-ori',
  semanticTags: ['物質'],
  associationTags: ['冷たい'],
  textureTags: ['硬い'],
  reviewStatus: 'draft',
};

const database: WordDatabase = {
  version: 'test',
  exportedAt: '',
  words: [sharishari, ice],
  relations: [{ from: 'a', to: 'b', type: 'association', weight: 1 }],
};

describe('rhythmSimilarity', () => {
  it('supports incremental prefix matching', () => {
    expect(rhythmSimilarity([1, 2], [1, 2, 1, 2])).toBe(1);
  });

  it('scores adjacent pitch levels as a near match', () => {
    expect(rhythmSimilarity([1, 1], [1, 2])).toBeCloseTo(0.725);
  });
});

describe('context ranking', () => {
  it('reads direct associations from the relation graph', () => {
    expect(associationSimilarity(database, sharishari, ice)).toBe(1);
  });

  it('keeps exact rhythm matches first', () => {
    const results = rankWords(database, [1, 2], null);
    expect(results[0]?.word.id).toBe('a');
  });

  it('matches a manually retained rhythm variant', () => {
    const word: WordEntry = {
      ...sharishari,
      rhythmShape: [2, 1, 1, 0],
      rhythmVariants: [[2, 1, 1, 0], [1, 2, 1, 2]],
    };
    const result = rankWords({ ...database, words: [word] }, [1, 2, 1, 2], null);
    expect(result[0]?.score.rhythm).toBe(1);
  });

  it('searches the expanded Japanese lexicon for a four-note contour', () => {
    const results = rankWords(generatedDatabase as WordDatabase, [1, 2, 1, 0], null, 5000);
    const ids = results.map(({ word }) => word.id);

    expect(results.length).toBeGreaterThan(1000);
    expect(ids).toContain('ja-karakara');
    expect(ids).toContain('ja-tsumetai');
    expect(ids).toContain('ja-komakai');
    expect(ids.some((id) => id.startsWith('jmdict-'))).toBe(true);
  });
});
