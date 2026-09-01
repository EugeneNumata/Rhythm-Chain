import type {
  PitchLevel,
  RankedWord,
  ScoreBreakdown,
  WordDatabase,
  WordEntry,
} from '../types';

export const SCORE_WEIGHTS = Object.freeze({
  rhythm: 0.4,
  rhyme: 0.25,
  semantic: 0.2,
  association: 0.15,
});

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

export function rhythmSimilarity(input: PitchLevel[], candidate: PitchLevel[]): number {
  if (input.length === 0) return 0;
  if (candidate.length === 0) return 0;

  let points = 0;
  for (let index = 0; index < input.length; index += 1) {
    const candidatePoint = candidate[index];
    if (candidatePoint === undefined) continue;
    const difference = Math.abs(input[index] - candidatePoint);
    points += difference === 0 ? 1 : difference === 1 ? 0.45 : 0.05;
  }

  return clamp01(points / input.length);
}

function longestCommonSuffix(left: string, right: string): number {
  let length = 0;
  const limit = Math.min(left.length, right.length, 6);
  while (length < limit && left[left.length - 1 - length] === right[right.length - 1 - length]) {
    length += 1;
  }
  return length;
}

export function rhymeSimilarity(previous: WordEntry | null, candidate: WordEntry): number {
  if (!previous) return 0;
  if (previous.rhymeFamily && previous.rhymeFamily === candidate.rhymeFamily) return 1;

  const previousPattern = previous.vowelPattern || previous.reading || previous.word.toLowerCase();
  const candidatePattern = candidate.vowelPattern || candidate.reading || candidate.word.toLowerCase();
  const suffix = longestCommonSuffix(previousPattern, candidatePattern);
  return clamp01(suffix / Math.min(4, Math.max(previousPattern.length, candidatePattern.length)));
}

function jaccard(left: string[], right: string[]): number {
  const leftSet = new Set(left.map((value) => value.toLowerCase()));
  const rightSet = new Set(right.map((value) => value.toLowerCase()));
  const union = new Set([...leftSet, ...rightSet]);
  if (union.size === 0) return 0;
  let intersection = 0;
  leftSet.forEach((value) => {
    if (rightSet.has(value)) intersection += 1;
  });
  return intersection / union.size;
}

export function semanticSimilarity(previous: WordEntry | null, candidate: WordEntry): number {
  if (!previous) return 0;
  return jaccard(
    [...previous.semanticTags, ...previous.textureTags],
    [...candidate.semanticTags, ...candidate.textureTags],
  );
}

export function associationSimilarity(
  database: WordDatabase,
  previous: WordEntry | null,
  candidate: WordEntry,
): number {
  if (!previous) return 0;

  const direct = database.relations.find(
    (relation) => relation.from === previous.id && relation.to === candidate.id,
  );
  const reverse = database.relations.find(
    (relation) => relation.to === previous.id && relation.from === candidate.id,
  );
  const tagHit = previous.associationTags.some(
    (tag) => tag.toLowerCase() === candidate.word.toLowerCase(),
  );
  const reverseTagHit = candidate.associationTags.some(
    (tag) => tag.toLowerCase() === previous.word.toLowerCase(),
  );
  const sharedTags = jaccard(previous.associationTags, candidate.associationTags) * 0.6;

  return clamp01(
    Math.max(direct?.weight ?? 0, (reverse?.weight ?? 0) * 0.8, tagHit ? 1 : 0, reverseTagHit ? 0.8 : 0, sharedTags),
  );
}

export function scoreWord(
  database: WordDatabase,
  input: PitchLevel[],
  previous: WordEntry | null,
  candidate: WordEntry,
): ScoreBreakdown {
  const rhythmShapes = candidate.rhythmVariants?.length
    ? candidate.rhythmVariants
    : [candidate.rhythmShape];
  const rhythm = Math.max(...rhythmShapes.map((shape) => rhythmSimilarity(input, shape)));
  const rhyme = rhymeSimilarity(previous, candidate);
  const semantic = semanticSimilarity(previous, candidate);
  const association = associationSimilarity(database, previous, candidate);
  const total =
    rhythm * SCORE_WEIGHTS.rhythm +
    rhyme * SCORE_WEIGHTS.rhyme +
    semantic * SCORE_WEIGHTS.semantic +
    association * SCORE_WEIGHTS.association;

  return { rhythm, rhyme, semantic, association, total };
}

export function rankWords(
  database: WordDatabase,
  input: PitchLevel[],
  previous: WordEntry | null,
  limit = 20,
): RankedWord[] {
  if (input.length === 0) return [];

  return database.words
    .filter((word) => word.reviewStatus !== 'rejected' && word.id !== previous?.id)
    .map((word) => ({ word, score: scoreWord(database, input, previous, word) }))
    .filter(({ score }) => score.rhythm > 0 || score.association >= 0.7)
    .sort((left, right) => {
      if (right.score.total !== left.score.total) return right.score.total - left.score.total;
      if (right.score.rhythm !== left.score.rhythm) return right.score.rhythm - left.score.rhythm;
      return left.word.word.localeCompare(right.word.word, 'ja');
    })
    .slice(0, limit);
}
