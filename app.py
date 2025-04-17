import streamlit as st
import anthropic
import os
import json
import time
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import httpx
import logging
import sys

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# API設定をロード - Streamlit Cloudとローカル環境の両方に対応
try:
    # Streamlit Cloud環境の場合
    ANTHROPIC_API_KEY = st.secrets["anthropic"]["api_key"]
    logger.info("Streamlit Cloud環境でAPIキーを取得しました")
except Exception as e:
    # ローカル環境の場合
    load_dotenv()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    logger.info("ローカル環境でAPIキーを取得しました")
    logger.error(f"APIキー取得エラー（発生した場合）: {str(e)}")

# APIキー情報のログ（セキュリティのため先頭5文字のみ）
if ANTHROPIC_API_KEY:
    api_key_preview = ANTHROPIC_API_KEY[:5] + "..." if len(ANTHROPIC_API_KEY) > 5 else "未設定"
    logger.info(f"APIキー: {api_key_preview}")
else:
    logger.error("APIキーが設定されていません")
    st.error("APIキーが設定されていません。.envファイルまたはStreamlit Secretsで設定してください。")

# HTTP クライアントのカスタム設定 (プロキシに関連するエラーを回避)
try:
    logger.info("HTTPクライアントを初期化しています...")
    http_client = httpx.Client(
        timeout=httpx.Timeout(60.0)  # タイムアウト設定
    )
    logger.info("HTTPクライアント初期化完了")
except Exception as e:
    logger.error(f"HTTPクライアント初期化エラー: {str(e)}")
    http_client = None

# Claude APIクライアントを初期化 - カスタム HTTP クライアントを使用
try:
    logger.info("Anthropic APIクライアントを初期化中...")
    if http_client:
        client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY,
            http_client=http_client
        )
    else:
        client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY
        )
    logger.info("Anthropic APIクライアント初期化完了")
except Exception as e:
    logger.error(f"Anthropic APIクライアント初期化エラー: {str(e)}")
    client = None
    st.error(f"APIクライアントの初期化中にエラーが発生しました: {str(e)}")

# Anthropicライブラリのバージョン確認
if 'anthropic' in sys.modules:
    logger.info(f"Anthropicライブラリバージョン: {anthropic.__version__}")

# アプリケーションのタイトルとスタイル
st.set_page_config(
    page_title="SEO ブログ記事生成ツール",
    page_icon="✍️",
    layout="wide",
)

# セッション状態の初期化
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'keyword' not in st.session_state:
    st.session_state.keyword = ""
if 'titles' not in st.session_state:
    st.session_state.titles = []
if 'selected_title' not in st.session_state:
    st.session_state.selected_title = ""
if 'article_structure' not in st.session_state:
    st.session_state.article_structure = {}
if 'article' not in st.session_state:
    st.session_state.article = ""
if 'edited_article' not in st.session_state:
    st.session_state.edited_article = ""
if 'seo_score' not in st.session_state:
    st.session_state.seo_score = {}
if 'related_keywords' not in st.session_state:
    st.session_state.related_keywords = []
if 'generating_titles' not in st.session_state:
    st.session_state.generating_titles = False
if 'generating_structure' not in st.session_state:
    st.session_state.generating_structure = False
if 'generating_article' not in st.session_state:
    st.session_state.generating_article = False
if 'current_section' not in st.session_state:
    st.session_state.current_section = 0
if 'total_sections' not in st.session_state:
    st.session_state.total_sections = 0
if 'section_contents' not in st.session_state:
    st.session_state.section_contents = {}
if 'progress' not in st.session_state:
    st.session_state.progress = 0
if 'debug_info' not in st.session_state:
    st.session_state.debug_info = []

# デバッグ情報を追加する関数
def add_debug_info(info):
    st.session_state.debug_info.append(f"{datetime.now().strftime('%H:%M:%S')} - {info}")
    # 最大100件までログを保持
    if len(st.session_state.debug_info) > 100:
        st.session_state.debug_info = st.session_state.debug_info[-100:]
    logger.info(info)

# ナビゲーション関数
def next_step():
    st.session_state.step += 1
    st.rerun()

def prev_step():
    st.session_state.step -= 1
    st.rerun()

def go_to_step(step):
    st.session_state.step = step
    st.rerun()

# 非同期タイトル生成を処理する関数
def process_title_generation():
    # タイトル生成中フラグを設定
    st.session_state.generating_titles = True
    
    # キーワードを取得
    keyword = st.session_state.keyword
    add_debug_info(f"タイトル生成開始: キーワード '{keyword}'")
    
    # タイトルと関連キーワードを生成
    titles = generate_titles(keyword)
    add_debug_info(f"タイトル生成結果: {len(titles)}件")
    
    if not titles or len(titles) == 0:
        add_debug_info("タイトル生成に失敗しました。空のリストが返されました。")
        st.session_state.titles = []
    else:
        st.session_state.titles = titles
        add_debug_info(f"生成されたタイトル: {titles}")
    
    # 関連キーワード生成
    try:
        related_keywords = suggest_related_keywords(keyword)
        st.session_state.related_keywords = related_keywords
        add_debug_info(f"関連キーワード生成結果: {len(related_keywords)}件")
    except Exception as e:
        add_debug_info(f"関連キーワード生成エラー: {str(e)}")
        st.session_state.related_keywords = []
    
    # 生成完了フラグを設定
    st.session_state.generating_titles = False
    
    # 次のステップに進む
    if titles and len(titles) > 0:
        st.session_state.step = 2
        st.rerun()
    else:
        add_debug_info("タイトルが生成されなかったため、次のステップに進みません")

# 記事構造の生成を処理する関数
def process_structure_generation():
    # 構造生成中フラグを設定
    st.session_state.generating_structure = True
    
    # タイトルとキーワードを取得
    selected_title = st.session_state.selected_title
    keyword = st.session_state.keyword
    add_debug_info(f"記事構造生成開始: タイトル '{selected_title}', キーワード '{keyword}'")
    
    # 記事構造を生成
    structure = generate_article_structure(selected_title, keyword)
    
    # 結果をセッション状態に保存
    st.session_state.article_structure = structure
    st.session_state.total_sections = len(structure["sections"])
    st.session_state.current_section = 0
    st.session_state.section_contents = {}
    st.session_state.generating_structure = False
    
    add_debug_info(f"記事構造生成完了: {st.session_state.total_sections}セクション")
    
    # 記事生成ステップに進む
    st.session_state.step = 3
    st.rerun()

# 記事本文の生成を処理する関数
def process_article_generation():
    # 記事生成中フラグを設定
    st.session_state.generating_article = True
    
    # 各セクションの内容を生成
    title = st.session_state.selected_title
    keyword = st.session_state.keyword
    structure = st.session_state.article_structure
    
    add_debug_info(f"記事生成開始: タイトル '{title}', キーワード '{keyword}'")
    
    # 進捗バーの初期化
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    # 記事の各パートを生成
    full_article = f"# {title}\n\n"
    
    # 導入部を生成
    progress_text.text("導入部を生成中...")
    add_debug_info("導入部の生成を開始")
    introduction = generate_article_part(title, keyword, structure, "introduction")
    full_article += introduction + "\n\n"
    st.session_state.section_contents["introduction"] = introduction
    progress_bar.progress(0.1)
    add_debug_info("導入部の生成完了")
    
    # 各セクションを生成
    total_sections = len(structure["sections"])
    for i, section in enumerate(structure["sections"]):
        section_name = f"section_{i+1}"
        heading = section.get('heading', f'セクション{i+1}')
        progress_text.text(f"セクション {i+1}/{total_sections} を生成中: {heading}...")
        add_debug_info(f"セクション {i+1}/{total_sections} '{heading}' の生成を開始")
        
        # セクションの内容を生成
        section_content = generate_article_part(title, keyword, structure, section_name, section_index=i)
        full_article += section_content + "\n\n"
        st.session_state.section_contents[section_name] = section_content
        
        # 進捗を更新
        progress = 0.1 + (0.8 * (i + 1) / total_sections)
        progress_bar.progress(progress)
        st.session_state.progress = progress
        st.session_state.current_section = i + 1
        add_debug_info(f"セクション {i+1}/{total_sections} の生成完了")
    
    # 結論部を生成
    progress_text.text("結論部を生成中...")
    add_debug_info("結論部の生成を開始")
    conclusion = generate_article_part(title, keyword, structure, "conclusion")
    full_article += conclusion
    st.session_state.section_contents["conclusion"] = conclusion
    progress_bar.progress(1.0)
    progress_text.text("記事生成が完了しました！")
    add_debug_info("結論部の生成完了")
    
    # 結果をセッション状態に保存
    st.session_state.article = full_article
    st.session_state.edited_article = full_article
    
    # SEO分析を実行
    add_debug_info("SEO分析を開始")
    st.session_state.seo_score = analyze_seo(full_article, keyword)
    add_debug_info("SEO分析完了")
    
    # 生成完了フラグを設定
    st.session_state.generating_article = False
    
    # 編集ステップに進む
    st.session_state.step = 4
    st.rerun()

# タイトル生成関数
def generate_titles(keyword):
    try:
        add_debug_info(f"API呼び出し開始: タイトル生成 (キーワード: {keyword})")
        
        # APIクライアントが初期化されているか確認
        if client is None:
            add_debug_info("エラー: APIクライアントが初期化されていません")
            return []
        
        # モデル名の確認
        model_name = "claude-3-7-sonnet-20250219"
        add_debug_info(f"使用モデル: {model_name}")
        
        # システムプロンプトのロギング
        system_prompt = "あなたはSEOの専門家です。与えられたキーワードに基づいて、SEO最適化された魅力的なブログタイトルを5つ提案してください。タイトルのリストのみを提供してください。"
        add_debug_info(f"システムプロンプト: {system_prompt}")
        
        # ユーザープロンプトのロギング
        user_prompt = f"以下のキーワードに基づいて、SEO最適化された魅力的なブログタイトルを5つ提案してください。タイトルのみをリストで返してください。キーワード：{keyword}"
        add_debug_info(f"ユーザープロンプト: {user_prompt}")
        
        # APIリクエスト開始
        start_time = time.time()
        response = client.messages.create(
            model=model_name,
            max_tokens=1000,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        end_time = time.time()
        
        # レスポンス時間のロギング
        add_debug_info(f"API応答時間: {end_time - start_time:.2f}秒")
        
        # レスポンスの内容をログに記録（デバッグ用）
        response_content = response.content[0].text if response and hasattr(response, 'content') and len(response.content) > 0 else "レスポンスが空です"
        add_debug_info(f"APIレスポンス: {response_content[:200]}...")  # 最初の200文字だけログに記録
        
        # レスポンスをチェック
        if not response or not hasattr(response, 'content') or len(response.content) == 0:
            add_debug_info("エラー: APIレスポンスが空です")
            return []
        
        # 特殊タグのチェック
        titles_text = response.content[0].text
        if "<search_reminders>" in titles_text or "<automated_reminder_from_anthropic>" in titles_text:
            add_debug_info("警告: APIレスポンスに特殊タグが含まれています")
            # 特殊タグを削除
            titles_text = titles_text.replace("<search_reminders>", "")
            titles_text = titles_text.replace("</search_reminders>", "")
            titles_text = titles_text.replace("<automated_reminder_from_anthropic>", "")
            titles_text = titles_text.replace("</automated_reminder_from_anthropic>", "")
        
        # タイトルのリストを作成
        titles_list = [line.strip() for line in titles_text.split('\n') if line.strip()]
        add_debug_info(f"抽出されたタイトル数: {len(titles_list)}")
        
        return titles_list
    except Exception as e:
        add_debug_info(f"タイトル生成中にエラーが発生しました: {str(e)}")
        # エラーのスタックトレースをログに記録
        import traceback
        add_debug_info(f"エラースタックトレース: {traceback.format_exc()}")
        return []

# 記事構造生成関数
def generate_article_structure(title, keyword):
    try:
        add_debug_info(f"API呼び出し開始: 記事構造生成 (タイトル: {title}, キーワード: {keyword})")
        
        prompt = f"""
        タイトル：{title}
        キーワード：{keyword}
        
        上記のタイトルとキーワードに基づいて、SEO最適化されたブログ記事の構成を作成してください。
        以下のフォーマットで、JSONとして返してください：

        {{
            "meta": {{
                "title": "記事のタイトル",
                "keyword": "メインキーワード",
                "target_audience": "ターゲット読者の説明",
                "word_count": 予想される単語数
            }},
            "introduction": "導入部の説明 (約100文字)",
            "sections": [
                {{
                    "heading": "セクション1の見出し (H2)",
                    "subheadings": [
                        "サブセクション1の見出し (H3)",
                        "サブセクション2の見出し (H3)"
                    ],
                    "keywords": ["このセクションに含めるべきキーワード"],
                    "content_brief": "このセクションで扱う内容の簡単な説明 (約100文字)"
                }},
                // 4-6個のセクションを提案
            ],
            "conclusion": "結論部の説明 (約100文字)"
        }}
        
        JSONデータのみを返してください。説明文は不要です。
        """
        
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=2000,
            temperature=0.7,
            system="あなたはSEOとブログ記事構成の専門家です。タイトルとキーワードに基づいて最適な記事構成をJSON形式で提案してください。結果はJSON形式のみで返してください。",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        end_time = time.time()
        add_debug_info(f"API応答時間: {end_time - start_time:.2f}秒")
        
        # レスポンスの内容をログに記録（デバッグ用）
        response_content = response.content[0].text if response and hasattr(response, 'content') and len(response.content) > 0 else "レスポンスが空です"
        add_debug_info(f"APIレスポンス: {response_content[:200]}...")  # 最初の200文字だけログに記録
        
        # レスポンスをチェック
        if not response or not hasattr(response, 'content') or len(response.content) == 0:
            add_debug_info("エラー: APIレスポンスが空です")
            return {
                "meta": {"title": title, "keyword": keyword, "target_audience": "一般読者", "word_count": 1500},
                "introduction": "導入部",
                "sections": [{"heading": "セクション1", "subheadings": [], "keywords": [keyword], "content_brief": "内容の説明"}],
                "conclusion": "結論部"
            }
        
        # 特殊タグをチェック
        structure_text = response.content[0].text
        if "<search_reminders>" in structure_text or "<automated_reminder_from_anthropic>" in structure_text:
            add_debug_info("警告: APIレスポンスに特殊タグが含まれています")
            # 特殊タグを削除
            structure_text = structure_text.replace("<search_reminders>", "")
            structure_text = structure_text.replace("</search_reminders>", "")
            structure_text = structure_text.replace("<automated_reminder_from_anthropic>", "")
            structure_text = structure_text.replace("</automated_reminder_from_anthropic>", "")
        
        # JSONを抽出（余分なテキストがある場合）
        if "{" in structure_text and "}" in structure_text:
            json_start = structure_text.find("{")
            json_end = structure_text.rfind("}") + 1
            structure_text = structure_text[json_start:json_end]
        
        add_debug_info(f"解析するJSON: {structure_text[:200]}...")
        
        # JSONをパース
        structure = json.loads(structure_text)
        add_debug_info(f"記事構造の解析成功: {len(structure.get('sections', []))}セクション")
        
        return structure
    except Exception as e:
        add_debug_info(f"記事構造生成中にエラーが発生しました: {str(e)}")
        # エラーのスタックトレースをログに記録
        import traceback
        add_debug_info(f"エラースタックトレース: {traceback.format_exc()}")
        return {
            "meta": {"title": title, "keyword": keyword, "target_audience": "一般読者", "word_count": 1500},
            "introduction": "導入部",
            "sections": [{"heading": "セクション1", "subheadings": [], "keywords": [keyword], "content_brief": "内容の説明"}],
            "conclusion": "結論部"
        }

# 記事パート生成関数
def generate_article_part(title, keyword, structure, part_type, section_index=None):
    try:
        add_debug_info(f"API呼び出し開始: 記事パート生成 (パートタイプ: {part_type}, セクションインデックス: {section_index})")
        
        # 記事全体の構造をJSON文字列に変換
        structure_json = json.dumps(structure, ensure_ascii=False, indent=2)
        
        # パート別のプロンプトを作成
        if part_type == "introduction":
            prompt = f"""
            タイトル：{title}
            キーワード：{keyword}
            
            以下の記事構造に基づいて、導入部分のみを作成してください：
            
            {structure_json}
            
            導入部は、次の点を含めてください：
            1. 読者の興味を引く冒頭文
            2. 記事の概要と解決する問題の説明
            3. メインキーワード「{keyword}」を自然に含める
            4. この記事で読者が得られるメリットの説明
            
            マークダウン形式で導入部分のみを作成してください。見出しは含めないでください。
            """
        elif part_type == "conclusion":
            prompt = f"""
            タイトル：{title}
            キーワード：{keyword}
            
            以下の記事構造に基づいて、結論部分のみを作成してください：
            
            {structure_json}
            
            結論部は、次の点を含めてください：
            1. 記事の主要ポイントの要約
            2. メインキーワード「{keyword}」を自然に含める
            3. 読者へのアクションの呼びかけ（可能であれば）
            4. 最後の印象的な締めの文
            
            マークダウン形式で結論部分のみを作成してください。「まとめ」や「結論」などの見出しを含めてください。
            """
        else:  # セクション
            section = structure["sections"][section_index]
            heading = section["heading"]
            subheadings = section.get("subheadings", [])
            section_keywords = section.get("keywords", [keyword])
            content_brief = section.get("content_brief", "")
            
            prompt = f"""
            タイトル：{title}
            メインキーワード：{keyword}
            セクション見出し：{heading}
            セクションキーワード：{', '.join(section_keywords)}
            セクション概要：{content_brief}
            
            以下の記事構造の一部として、このセクションのみを作成してください：
            
            {structure_json}
            
            このセクションでは、次の点を含めてください：
            1. セクション見出し「{heading}」をH2見出し(##)として使用
            2. サブ見出し {', '.join([f'「{sh}」' for sh in subheadings])}をH3見出し(###)として使用（存在する場合）
            3. セクションキーワードを自然に含める
            4. 具体的な例、事例、または統計データ
            5. 読者にとって実用的な情報
            
            マークダウン形式でこのセクションのみを作成してください。他のセクションは含めないでください。
            """
        
        add_debug_info(f"生成プロンプト: {prompt[:200]}...")  # プロンプトの最初の部分だけログに記録
        
        # パートを生成 - max_tokensを大きく設定
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            temperature=0.7,
            system="あなたはSEOと内容に優れたブログ記事の執筆者です。与えられた情報に基づいて、高品質なブログ記事のパートを作成してください。マークダウン形式で返してください。",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        end_time = time.time()
        add_debug_info(f"API応答時間: {end_time - start_time:.2f}秒")
        
        # レスポンスの内容をログに記録（デバッグ用）
        response_content = response.content[0].text if response and hasattr(response, 'content') and len(response.content) > 0 else "レスポンスが空です"
        add_debug_info(f"APIレスポンス: {response_content[:200]}...")  # 最初の200文字だけログに記録
        
        # レスポンスをチェック
        if not response or not hasattr(response, 'content') or len(response.content) == 0:
            add_debug_info("エラー: APIレスポンスが空です")
            if part_type == "introduction":
                return "## はじめに\n\nこのブログ記事では、重要なトピックについて解説します。"
            elif part_type == "conclusion":
                return "## まとめ\n\nこの記事の要点をまとめました。"
            else:
                return f"## セクション {section_index + 1}\n\nこのセクションでは重要な情報を提供します。"
        
        # 特殊タグをチェック
        content_text = response.content[0].text
        if "<search_reminders>" in content_text or "<automated_reminder_from_anthropic>" in content_text:
            add_debug_info("警告: APIレスポンスに特殊タグが含まれています")
            # 特殊タグを削除
            content_text = content_text.replace("<search_reminders>", "")
            content_text = content_text.replace("</search_reminders>", "")
            content_text = content_text.replace("<automated_reminder_from_anthropic>", "")
            content_text = content_text.replace("</automated_reminder_from_anthropic>", "")
            return content_text
        
        return response.content[0].text
    except Exception as e:
        add_debug_info(f"記事パート生成中にエラーが発生しました: {str(e)}")
        # エラーのスタックトレースをログに記録
        import traceback
        add_debug_info(f"エラースタックトレース: {traceback.format_exc()}")
        if part_type == "introduction":
            return "## はじめに\n\nこのブログ記事では、重要なトピックについて解説します。"
        elif part_type == "conclusion":
            return "## まとめ\n\nこの記事の要点をまとめました。"
        else:
            return f"## セクション {section_index + 1}\n\nこのセクションでは重要な情報を提供します。"

# SEO分析関数
def analyze_seo(article, keyword):
    try:
        add_debug_info(f"API呼び出し開始: SEO分析 (キーワード: {keyword}, 記事長: {len(article)} 文字)")
        
        prompt = f"""
        以下の記事とキーワードに基づいて、SEO分析を行ってください。
        
        キーワード：{keyword}
        
        記事：
        {article[:3000]}...
        
        以下の項目について分析し、それぞれ0-100のスコアを付けてください：
        1. キーワード密度
        2. タイトルの最適化
        3. 見出しの使用
        4. 内部リンクの可能性
        5. コンテンツの品質
        6. 読みやすさ
        7. 総合SEOスコア
        
        JSONフォーマットで結果を返してください。例：
        {{"keyword_density": 85, "title_optimization": 90, "headings": 80, "internal_links": 70, "content_quality": 85, "readability": 90, "overall_score": 83}}
        """
        
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=1000,
            temperature=0.2,
            system="あなたはSEO分析の専門家です。提供された記事とキーワードに基づいて、客観的なSEO分析を行ってください。",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        end_time = time.time()
        add_debug_info(f"API応答時間: {end_time - start_time:.2f}秒")
        
        # レスポンスの内容をログに記録（デバッグ用）
        response_content = response.content[0].text if response and hasattr(response, 'content') and len(response.content) > 0 else "レスポンスが空です"
        add_debug_info(f"APIレスポンス: {response_content[:200]}...")  # 最初の200文字だけログに記録
        
        # レスポンスをチェック
        if not response or not hasattr(response, 'content') or len(response.content) == 0:
            add_debug_info("エラー: APIレスポンスが空です")
            return {"keyword_density": 0, "title_optimization": 0, "headings": 0, "internal_links": 0, "content_quality": 0, "readability": 0, "overall_score": 0}
        
        # 特殊タグをチェック
        json_str = response.content[0].text.strip()
        if "<search_reminders>" in json_str or "<automated_reminder_from_anthropic>" in json_str:
            add_debug_info("警告: APIレスポンスに特殊タグが含まれています")
            # 特殊タグを削除
            json_str = json_str.replace("<search_reminders>", "")
            json_str = json_str.replace("</search_reminders>", "")
            json_str = json_str.replace("<automated_reminder_from_anthropic>", "")
            json_str = json_str.replace("</automated_reminder_from_anthropic>", "")
        
        # JSON部分を抽出（余分なテキストがある場合）
        if "{" in json_str and "}" in json_str:
            json_str = json_str[json_str.find("{"):json_str.rfind("}")+1]
        
        add_debug_info(f"解析するJSON: {json_str}")
        
        return json.loads(json_str)
    except Exception as e:
        add_debug_info(f"SEO分析中にエラーが発生しました: {str(e)}")
        # エラーのスタックトレースをログに記録
        import traceback
        add_debug_info(f"エラースタックトレース: {traceback.format_exc()}")
        return {"keyword_density": 0, "title_optimization": 0, "headings": 0, "internal_links": 0, "content_quality": 0, "readability": 0, "overall_score": 0}

# 関連キーワード生成関数
def suggest_related_keywords(keyword):
    try:
        add_debug_info(f"API呼び出し開始: 関連キーワード生成 (キーワード: {keyword})")
        
        start_time = time.time()
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=1000,
            temperature=0.7,
            system="あなたはSEOとキーワードリサーチの専門家です。主要キーワードに関連する効果的なキーワードを提案してください。",
            messages=[
                {"role": "user", "content": f"以下の主要キーワードに関連する10個のキーワードを提案してください。シンプルなリスト形式で返してください。主要キーワード：{keyword}"}
            ]
        )
        end_time = time.time()
        add_debug_info(f"API応答時間: {end_time - start_time:.2f}秒")
        
        # レスポンスの内容をログに記録（デバッグ用）
        response_content = response.content[0].text if response and hasattr(response, 'content') and len(response.content) > 0 else "レスポンスが空です"
        add_debug_info(f"APIレスポンス: {response_content[:200]}...")  # 最初の200文字だけログに記録
        
        # レスポンスをチェック
        if not response or not hasattr(response, 'content') or len(response.content) == 0:
            add_debug_info("エラー: APIレスポンスが空です")
            return []
        
        # 特殊タグをチェック
        keywords_text = response.content[0].text
        if "<search_reminders>" in keywords_text or "<automated_reminder_from_anthropic>" in keywords_text:
            add_debug_info("警告: APIレスポンスに特殊タグが含まれています")
            # 特殊タグを削除
            keywords_text = keywords_text.replace("<search_reminders>", "")
            keywords_text = keywords_text.replace("</search_reminders>", "")
            keywords_text = keywords_text.replace("<automated_reminder_from_anthropic>", "")
            keywords_text = keywords_text.replace("</automated_reminder_from_anthropic>", "")
        
        # キーワードのリストを作成
        keywords_list = [line.strip() for line in keywords_text.split('\n') if line.strip()]
        add_debug_info(f"抽出された関連キーワード数: {len(keywords_list)}")
        
        return keywords_list
    except Exception as e:
        add_debug_info(f"関連キーワード生成中にエラーが発生しました: {str(e)}")
        # エラーのスタックトレースをログに記録
        import traceback
        add_debug_info(f"エラースタックトレース: {traceback.format_exc()}")
        return []

# 記事を保存する関数
def save_article(title, article):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"blog_{timestamp}.md"
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(article)
        add_debug_info(f"記事を保存しました: {filename}")
        return filename
    except Exception as e:
        add_debug_info(f"記事の保存中にエラーが発生しました: {str(e)}")
        return None

# メイン画面表示
st.title("✍️ SEO ブログ記事生成ツール")

# ステップ1: キーワード入力
if st.session_state.step == 1:
    st.header("ステップ 1: キーワードを入力してください")
    
    st.write("作成したいブログ記事のメインキーワードを入力してください。")
    keyword = st.text_input("メインキーワード", st.session_state.keyword)
    
    # タイトル生成中の表示
    if st.session_state.generating_titles:
        st.info("タイトルを生成中です。しばらくお待ちください...")
        st.spinner("タイトルを生成中...")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("タイトル生成", key="gen_titles"):
            if keyword:
                st.session_state.keyword = keyword
                process_title_generation()  # 非同期処理関数を呼び出し
            else:
                st.warning("キーワードを入力してください。")

# ステップ2: タイトル選択
elif st.session_state.step == 2:
    st.header("ステップ 2: タイトルを選択してください")
    
    st.write(f"キーワード「{st.session_state.keyword}」に基づいて、以下のタイトル候補が生成されました。")
    
    # 構造生成中の表示
    if st.session_state.generating_structure:
        st.info("記事の構成を生成中です。しばらくお待ちください...")
        st.spinner("記事構成を生成中...")
    
    if st.session_state.titles:
        selected_title = st.radio("タイトルを選択", st.session_state.titles)
        
        # 関連キーワードを表示
        if st.session_state.related_keywords:
            with st.expander("関連キーワード（記事に含めるとSEO効果が高まります）", expanded=True):
                related_keywords = st.session_state.related_keywords
                # 関連キーワードを2列で表示
                cols = st.columns(2)
                for i, kw in enumerate(related_keywords):
                    cols[i % 2].write(f"- {kw}")
        
        col1, col2, col3 = st.columns([1, 1, 5])
        with col1:
            if st.button("戻る", key="back_to_1"):
                prev_step()
        with col2:
            if st.button("記事構成を生成", key="gen_structure"):
                if selected_title:
                    st.session_state.selected_title = selected_title
                    process_structure_generation()  # 構造生成処理関数を呼び出し
                else:
                    st.warning("タイトルを選択してください。")
    else:
        st.warning("タイトルが生成されませんでした。キーワードを変更して再試行してください。")
        if st.button("キーワード入力に戻る"):
            prev_step()

# ステップ3: 記事構造確認と生成開始
elif st.session_state.step == 3:
    st.header("ステップ 3: 記事構成を確認し、記事を生成してください")
    
    # 記事生成中の表示
    if st.session_state.generating_article:
        st.info(f"記事を生成中です... ({st.session_state.current_section}/{st.session_state.total_sections} セクション完了)")
        st.progress(st.session_state.progress)
    else:
        structure = st.session_state.article_structure
        
        # 記事構造を表示
        st.subheader(f"タイトル: {st.session_state.selected_title}")
        st.write(f"キーワード: {st.session_state.keyword}")
        
        if "meta" in structure:
            meta = structure["meta"]
            st.write(f"対象読者: {meta.get('target_audience', '一般読者')}")
            st.write(f"予想単語数: 約{meta.get('word_count', 1500)}語")
        
        st.write("### 記事構成")
        st.write("**導入部**")
        st.write(structure.get("introduction", "導入部"))
        
        st.write("**本文**")
        for i, section in enumerate(structure.get("sections", [])):
            st.write(f"{i+1}. **{section.get('heading', f'セクション{i+1}')}**")
            for j, subheading in enumerate(section.get("subheadings", [])):
                st.write(f"   {i+1}.{j+1}. {subheading}")
            
        st.write("**結論**")
        st.write(structure.get("conclusion", "結論部"))
        
        col1, col2, col3 = st.columns([1, 1, 5])
        with col1:
            if st.button("タイトル選択に戻る", key="back_to_2"):
                prev_step()
        with col2:
            if st.button("記事を生成", key="gen_article"):
                process_article_generation()  # 記事生成処理関数を呼び出し

# ステップ4: 記事編集と保存
elif st.session_state.step == 4:
    st.header("ステップ 4: 記事を編集・保存")
    
    st.subheader(st.session_state.selected_title)
    
    # SEOスコアの表示
    st.sidebar.header("SEO分析")
    if st.session_state.seo_score:
        score = st.session_state.seo_score
        
        # 総合スコア
        st.sidebar.metric("総合SEOスコア", f"{score.get('overall_score', 0)}/100")
        
        # 詳細スコア
        st.sidebar.subheader("詳細スコア")
        cols = st.sidebar.columns(2)
        cols[0].metric("キーワード密度", f"{score.get('keyword_density', 0)}/100")
        cols[1].metric("タイトル最適化", f"{score.get('title_optimization', 0)}/100")
        cols[0].metric("見出し使用", f"{score.get('headings', 0)}/100")
        cols[1].metric("内部リンク", f"{score.get('internal_links', 0)}/100")
        cols[0].metric("コンテンツ品質", f"{score.get('content_quality', 0)}/100")
        cols[1].metric("読みやすさ", f"{score.get('readability', 0)}/100")
        
        # データをグラフ化
        st.sidebar.subheader("SEOスコアグラフ")
        score_data = {
            "項目": ["KW密度", "タイトル", "見出し", "内部リンク", "品質", "読みやすさ"],
            "スコア": [
                score.get('keyword_density', 0),
                score.get('title_optimization', 0),
                score.get('headings', 0),
                score.get('internal_links', 0),
                score.get('content_quality', 0),
                score.get('readability', 0)
            ]
        }
        score_df = pd.DataFrame(score_data)
        st.sidebar.bar_chart(score_df.set_index("項目"))
    
    # 記事編集エリア
    edited_article = st.text_area("記事を編集", st.session_state.edited_article, height=500)
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 5])
    with col1:
        if st.button("構成確認に戻る", key="back_to_3"):
            prev_step()
    with col2:
        if st.button("記事を保存", key="save_article"):
            if edited_article:
                st.session_state.edited_article = edited_article
                filename = save_article(st.session_state.selected_title, edited_article)
                if filename:
                    st.success(f"記事を保存しました: {filename}")
                    # 記事のダウンロードリンクを提供
                    try:
                        with open(filename, "r", encoding="utf-8") as f:
                            st.download_button(
                                label="記事をダウンロード",
                                data=f.read(),
                                file_name=filename,
                                mime="text/markdown"
                            )
                    except Exception as e:
                        st.error(f"ダウンロードリンクの作成中にエラーが発生しました: {e}")
    with col3:
        if st.button("最初から始める", key="restart"):
            # セッション状態をリセット
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # プレビュー表示
    with st.expander("記事プレビュー", expanded=True):
        st.markdown(edited_article)

# デバッグ情報表示
with st.expander("デバッグ情報", expanded=False):
    st.write("### ログ情報")
    for log in st.session_state.debug_info:
        st.write(log)
    
    st.write("### 環境情報")
    st.write(f"Streamlitバージョン: {st.__version__}")
    st.write(f"Anthropicライブラリバージョン: {anthropic.__version__ if 'anthropic' in sys.modules else '不明'}")
    st.write(f"セッション状態: {list(st.session_state.keys())}")
