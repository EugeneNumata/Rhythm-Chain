import { useEffect, useMemo, useState } from 'react';
import { rankWords } from './lib/search';
import { loadSession, saveSession } from './lib/storage';
import type { PitchLevel, StockItem, WordDatabase, WordEntry } from './types';

const PITCH_ROWS: Array<{ value: PitchLevel; label: string; symbol: string }> = [
  { value: 2, label: '高', symbol: '▲' },
  { value: 1, label: '中', symbol: '●' },
  { value: 0, label: '低', symbol: '▼' },
];

const emptyDatabase: WordDatabase = {
  version: '',
  exportedAt: '',
  words: [],
  relations: [],
};

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function makeStockItem(word: WordEntry): StockItem {
  return {
    id: `${Date.now()}-${crypto.randomUUID()}`,
    wordId: word.id,
    word: word.word,
    addedAt: new Date().toISOString(),
  };
}

export default function App() {
  const [database, setDatabase] = useState<WordDatabase>(emptyDatabase);
  const [databaseError, setDatabaseError] = useState('');
  const [sequence, setSequence] = useState<PitchLevel[]>([]);
  const [stock, setStock] = useState<StockItem[]>([]);
  const [restored, setRestored] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [notice, setNotice] = useState('');
  const [showSources, setShowSources] = useState(false);

  useEffect(() => {
    fetch('./data/db.json')
      .then((response) => {
        if (!response.ok) throw new Error(`DB load failed: ${response.status}`);
        return response.json() as Promise<WordDatabase>;
      })
      .then(setDatabase)
      .catch((error: unknown) => {
        setDatabaseError(error instanceof Error ? error.message : '単語DBを読み込めませんでした');
      });

    loadSession()
      .then((session) => {
        if (session) setStock(session.stock);
      })
      .catch(() => setNotice('保存データを読み込めませんでした'))
      .finally(() => setRestored(true));

    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    navigator.storage?.persist?.().catch(() => undefined);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (!restored) return;
    const timer = window.setTimeout(() => {
      saveSession({ stock, updatedAt: new Date().toISOString() }).catch(() => {
        setNotice('歌詞の自動保存に失敗しました');
      });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [restored, stock]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(''), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const previousWord = useMemo(() => {
    const last = stock.at(-1);
    return last ? database.words.find((word) => word.id === last.wordId) ?? null : null;
  }, [database.words, stock]);

  const candidates = useMemo(
    () => rankWords(database, sequence, previousWord, 24),
    [database, previousWord, sequence],
  );

  const choosePitch = (column: number, pitch: PitchLevel) => {
    setSequence((current) => {
      if (column > current.length) return current;
      if (column === current.length) return current.length < 10 ? [...current, pitch] : current;
      return current.map((value, index) => (index === column ? pitch : value));
    });
  };

  const adoptWord = (word: WordEntry) => {
    setStock((current) => [...current, makeStockItem(word)]);
    setSequence([]);
    setNotice(`♪ ${word.word} を追加`);
  };

  const undoLast = () => {
    setStock((current) => current.slice(0, -1));
  };

  const removeStockItem = (id: string) => {
    setStock((current) => current.filter((item) => item.id !== id));
  };

  const copyLyrics = async () => {
    if (stock.length === 0) return;
    const lyrics = stock.map((item) => item.word).join(' ｜ ');
    try {
      await navigator.clipboard.writeText(lyrics);
      setNotice('歌詞をコピーしました');
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = lyrics;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand('copy');
      textarea.remove();
      setNotice(copied ? '歌詞をコピーしました' : 'コピーできませんでした');
    }
  };

  const exportSession = () => {
    const blob = new Blob(
      [JSON.stringify({ version: 1, stock, exportedAt: new Date().toISOString() }, null, 2)],
      { type: 'application/json' },
    );
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `rhythm-chain-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">RAP WRITING TOOL</p>
          <h1>RHYTHM CHAIN</h1>
        </div>
        <div className="topbar-actions">
          <button type="button" className="sources-button" onClick={() => setShowSources(true)}>SOURCES</button>
          <div className={`connection-pill ${online ? 'online' : 'offline'}`}>
            <span aria-hidden="true" />
            {online ? 'READY' : 'OFFLINE'}
          </div>
        </div>
      </header>

      <main>
        <section className="context-panel" aria-label="直前の採用語">
          <span>CONTEXT</span>
          <strong>{previousWord?.word ?? '最初のリズムを選択'}</strong>
          {previousWord && <small>{previousWord.reading || previousWord.language.toUpperCase()}</small>}
        </section>

        <section className="rhythm-section" aria-labelledby="rhythm-title">
          <div className="section-heading">
            <div>
              <p>01 / RHYTHM INPUT</p>
              <h2 id="rhythm-title">高・中・低を左からタップ</h2>
            </div>
            <div className="rhythm-actions">
              <button type="button" onClick={() => setSequence((current) => current.slice(0, -1))} disabled={!sequence.length}>
                1つ戻す
              </button>
              <button type="button" onClick={() => setSequence([])} disabled={!sequence.length}>
                クリア
              </button>
            </div>
          </div>

          <div className="rhythm-grid" role="grid" aria-label="10拍のリズム選択">
            {PITCH_ROWS.map((row) => (
              <div className="pitch-row" role="row" key={row.value}>
                <span className="pitch-label">{row.label}</span>
                {Array.from({ length: 10 }, (_, column) => {
                  const selected = sequence[column] === row.value;
                  const enabled = column <= sequence.length;
                  return (
                    <button
                      type="button"
                      role="gridcell"
                      aria-label={`${column + 1}拍目 ${row.label}`}
                      aria-selected={selected}
                      className={`pitch-dot pitch-${row.value} ${selected ? 'selected' : ''}`}
                      disabled={!enabled}
                      key={column}
                      onClick={() => choosePitch(column, row.value)}
                    >
                      <span>{selected ? row.symbol : ''}</span>
                    </button>
                  );
                })}
              </div>
            ))}
            <div className="beat-numbers" aria-hidden="true">
              <span />
              {Array.from({ length: 10 }, (_, index) => <span key={index}>{index + 1}</span>)}
            </div>
          </div>

          <div className="sequence-strip">
            <span>SHAPE</span>
            <code>{sequence.length ? `[${sequence.join(',')}]` : 'タップすると即検索'}</code>
            <b>{sequence.length}/10</b>
          </div>
        </section>

        <section className="candidate-section" aria-labelledby="candidate-title">
          <div className="section-heading candidate-heading">
            <div>
              <p>02 / LIVE SUGGEST</p>
              <h2 id="candidate-title">候補</h2>
            </div>
            <span>{candidates.length} WORDS</span>
          </div>

          {databaseError && <div className="empty-state error">{databaseError}</div>}
          {!databaseError && sequence.length === 0 && (
            <div className="empty-state">
              <strong>丸を1つ選ぶと検索開始</strong>
              <span>入力するたびに候補が更新される</span>
            </div>
          )}
          {sequence.length > 0 && candidates.length === 0 && (
            <div className="empty-state">
              <strong>一致する語がまだない</strong>
              <span>DB生成後に候補が増えていく</span>
            </div>
          )}

          <div className="candidate-list">
            {candidates.map(({ word, score }, index) => (
              <article className="candidate-card" key={word.id}>
                <button type="button" className="adopt-button" onClick={() => adoptWord(word)} aria-label={`${word.word}を歌詞へ追加`}>
                  ♪
                </button>
                <div className="candidate-main">
                  <div className="candidate-word-row">
                    <div>
                      <span className="rank">{String(index + 1).padStart(2, '0')}</span>
                      <strong>{word.word}</strong>
                      <small>{word.reading || word.language.toUpperCase()}</small>
                    </div>
                    <b>{percent(score.total)}</b>
                  </div>
                  <div className="score-grid">
                    <span><i style={{ width: percent(score.rhythm) }} />RHYTHM {percent(score.rhythm)}</span>
                    <span><i style={{ width: percent(score.rhyme) }} />RHYME {percent(score.rhyme)}</span>
                    <span><i style={{ width: percent(score.semantic) }} />MEANING {percent(score.semantic)}</span>
                    <span><i style={{ width: percent(score.association) }} />LINK {percent(score.association)}</span>
                  </div>
                  <div className="tag-row">
                    {Array.from(new Set([...word.semanticTags, ...word.associationTags])).slice(0, 4).map((tag) => <em key={tag}>{tag}</em>)}
                    {word.rhythmShape.length === 0 && <em className="pending-tag">音形待ち</em>}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>

      <aside className="stock-bar" aria-label="歌詞ストック">
        <div className="stock-topline">
          <div><span>LYRIC STOCK</span><b>{stock.length}</b></div>
          <div className="stock-actions">
            <button type="button" onClick={undoLast} disabled={!stock.length}>戻す</button>
            <button type="button" onClick={exportSession} disabled={!stock.length}>保存</button>
            <button type="button" onClick={copyLyrics} disabled={!stock.length}>全文コピー</button>
          </div>
        </div>
        <div className="stock-track">
          {stock.length === 0 && <span className="stock-placeholder">♪を押した言葉がここへ並ぶ</span>}
          {stock.map((item, index) => (
            <div className="stock-chip" key={item.id}>
              <small>{index + 1}</small>
              <span>{item.word}</span>
              <button type="button" onClick={() => removeStockItem(item.id)} aria-label={`${item.word}を削除`}>×</button>
            </div>
          ))}
        </div>
      </aside>

      {showSources && (
        <div className="sources-overlay" role="presentation" onClick={() => setShowSources(false)}>
          <section className="sources-dialog" role="dialog" aria-modal="true" aria-labelledby="sources-title" onClick={(event) => event.stopPropagation()}>
            <div className="sources-title-row">
              <div>
                <span>DATA & LICENCE</span>
                <h2 id="sources-title">語彙データの出典</h2>
              </div>
              <button type="button" onClick={() => setShowSources(false)} aria-label="出典を閉じる">×</button>
            </div>
            <p>日本語語彙・読み・品詞・英語語義はEDRDGのJMdictを利用し、派生語彙データはCC BY-SA 4.0の対象です。</p>
            <a href="https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project" target="_blank" rel="noreferrer">JMdict / EDRDG</a>
            <a href="https://www.edrdg.org/edrdg/licence.html" target="_blank" rel="noreferrer">JMdict licence</a>
            <p>アクセント型はUniDic Lite 2.1.2を利用し、アプリ用の低・中・高へ変換しています。</p>
            <a href="https://github.com/polm/unidic-lite" target="_blank" rel="noreferrer">UniDic Lite</a>
            <small>自動生成の音高は作詞検索用の近似値です。文脈・話者・方言によって実際の発音は変わります。</small>
          </section>
        </div>
      )}

      {notice && <div className="toast" role="status">{notice}</div>}
    </div>
  );
}
