export type PitchLevel = 0 | 1 | 2;

export interface WordEntry {
  id: string;
  word: string;
  reading: string;
  language: string;
  rhythmShape: PitchLevel[];
  rhythmVariants?: PitchLevel[][];
  moraCount?: number;
  syllableCount?: number;
  vowelPattern: string;
  rhymeFamily: string;
  semanticTags: string[];
  associationTags: string[];
  textureTags: string[];
  reviewStatus: 'draft' | 'auto_generated' | 'reviewed' | 'rejected';
  pitchSource?: string;
  rhythmConfidence?: number;
  metadataConfidence?: number;
  partOfSpeech?: string;
  sourceId?: string;
  sourceUrl?: string;
  license?: string;
  glosses?: string[];
}

export interface WordRelation {
  from: string;
  to: string;
  type: 'rhyme' | 'semantic' | 'association' | 'attribute' | 'texture' | 'sound';
  weight: number;
}

export interface WordDatabase {
  version: string;
  exportedAt: string;
  words: WordEntry[];
  relations: WordRelation[];
  dataSources?: Array<{
    id: string;
    name: string;
    url: string;
    license: string;
    licenseUrl?: string;
  }>;
}

export interface ScoreBreakdown {
  rhythm: number;
  rhyme: number;
  semantic: number;
  association: number;
  total: number;
}

export interface RankedWord {
  word: WordEntry;
  score: ScoreBreakdown;
}

export interface StockItem {
  id: string;
  wordId: string;
  word: string;
  addedAt: string;
}

export interface SavedSession {
  stock: StockItem[];
  updatedAt: string;
}
