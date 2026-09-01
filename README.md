# Rhythm Chain

リズムの高・中・低をタップし、音の形から次の言葉を探す公開α版PWAです。iPhoneのホーム画面へ追加でき、語彙検索と作詞ストックは端末内で動作します。

> Experimental: 音高形状は辞書データから生成した検索用の近似値です。正式な東京式アクセントや、すべての文脈・方言における発音を保証するものではありません。

## 現在できること

- 3行×10列の高・中・低グリッドを左からタップ
- 1点目から候補をリアルタイム更新
- Rhythm / Rhyme / Meaning / Link の4軸でローカルランキング
- ♪で候補を歌詞ストックへ追加
- 戻す、個別削除、全文コピー、JSONバックアップ
- IndexedDBへの自動保存
- Service Workerによるオフライン起動

## 開発

```bash
npm install
npm run dev
```

検証：

```bash
npm run test
npm run build
```

## 単語DB

実行時データは`public/data/db.json`です。開発者側で編集・生成したスナップショットを、PWAが端末内で検索します。秘密トークンや個人用の編集元URLはPWAに含めません。

### 日本語語彙をJMdictから生成

初期シード13語は、意味・連想を手作業で調整する高品質語として残しています。通常の検索母集団は、JMdictの一般語とUniDic Liteのアクセント型から生成します。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-db.txt
.venv/bin/python scripts/import_jmdict.py --refresh --limit 2000 --write
```

既定値は日本語2,000語です。`--limit`で増減できます。JMdictの利用条件に従い、公開版では少なくとも月1回`--refresh`を実行してDBを更新します。出典・ライセンスは[THIRD_PARTY_DATA.md](./THIRD_PARTY_DATA.md)に記載しています。

### 日本語の3段階音高を生成

macOSの`Kyoko`音声で読みを発話し、モーラごとの基本周波数を単語内で相対量子化します。

```bash
.venv/bin/python scripts/quantize_pitch.py
.venv/bin/python scripts/quantize_pitch.py --write
```

`0=低 / 1=中 / 2=高`です。自動生成値には`pitchSource`と`rhythmConfidence`を付け、辞書上の確定アクセントとは区別します。

## iPhoneへの追加

HTTPSで公開されたURLをSafariで開き、共有メニューから「ホーム画面に追加」し、「Webアプリとして開く」を有効にします。一度オンラインで読み込んだ後は、キャッシュ済みのアプリとDBでオフライン起動できます。

## 公開範囲とライセンス

- 語彙データの出典と利用条件は[THIRD_PARTY_DATA.md](./THIRD_PARTY_DATA.md)を参照してください。
- JMdict由来の派生語彙データはCC BY-SA 4.0で公開します。
- アプリのソースコードに別途のオープンソースライセンスは付与していません。詳細は[LICENSE.md](./LICENSE.md)を参照してください。
