# Task 24A 涓ユ牸鍏ㄥ眬浠ｇ爜瀹℃煡鎶ュ憡

## 1. 瀹℃煡鑼冨洿

鏈瀹℃煡鏄彧璇诲璁★紝鐩爣鏄瘑鍒?Energy-Maintenance 褰撳墠璺濈浼佷笟绾т氦浠樸€佺湡瀹炶兘鍔涘０鏄庛€佸浗浜у寲 CPU-only 閮ㄧ讲鍜屽悗缁瓟杈╂潗鏂欎箣闂寸殑宸窛銆傛湰娆℃湭淇浠ｇ爜銆佹湭鏂板 migration銆佹湭鎵ц `alembic upgrade head`銆佹湭娓呯悊鏁版嵁銆佹湭鎵撳寘銆佹湭璋冪敤鐪熷疄澶栭儴 API銆?
宸茶鍙栧拰鎵弿鐨勪富瑕佽寖鍥达細

- 鏍圭洰褰曟枃妗ｏ細`README.md`銆乣AGENTS.md`
- 鍚庣鏂囨。锛歚backend/README.md`
- 椤圭洰鏂囨。锛歚docs/`
- 鍚庣浠ｇ爜锛歚backend/app/`
- 鍚庣杩佺Щ锛歚backend/alembic/versions/`
- 鍚庣鑴氭湰锛歚backend/scripts/`
- 鍓嶇婧愮爜锛歚frontend/src/`
- 鏍圭洰褰曡剼鏈細`scripts/`
- 閰嶇疆绀轰緥锛歚backend/.env.example`
- 鏈湴 `.env`锛氫粎妫€鏌?key 鍚嶇О鍜屾槸鍚︿负绌?鍗犱綅锛屼笉杈撳嚭浠讳綍鏁忔劅鍊?
杩愯鐨勯潤鎬侀獙璇佸懡浠わ細

- `uv run python -m compileall app scripts`
- `uv run python -m alembic -c alembic.ini current`
- `uv run python -m alembic -c alembic.ini heads`
- `npm.cmd run build`
- `git status --short`
- `Invoke-RestMethod http://127.0.0.1:8010/api/health`
- `Invoke-RestMethod http://127.0.0.1:8010/openapi.json`
- `Invoke-RestMethod http://127.0.0.1:8010/api/system/status`
- `Get-NetTCPConnection` 妫€鏌?8000銆?010銆?432銆?5432
- `Get-Service` 妫€鏌?PostgreSQL Windows service

鏄庣‘鏈墽琛岀殑楂橀闄╂搷浣滐細

- 鏈墽琛?`alembic upgrade head`
- 鏈墽琛?`Compress-Archive`
- 鏈敓鎴愭垨鏇存柊 delivery 鍖?- 鏈皟鐢ㄧ湡瀹?MIMO銆丱CR銆丆loud LLM銆丆loud Vision銆乴ocal llama.cpp
- 鏈畨瑁呬緷璧栥€佹湭涓嬭浇妯″瀷銆佹湭鍚姩 GPU 鎴栨湰鍦板ぇ妯″瀷
- 鏈竻鐞嗘暟鎹簱銆佹湭鍒犻櫎涓婁紶鏂囦欢
- 鏈墽琛?`git add` / `git commit`

## 2. 鎬讳綋缁撹

- 涓氬姟闂幆锛氭牳蹇冧笟鍔￠棴鐜凡缁忓叿澶囪緝瀹屾暣鐨?PostgreSQL 鎸佷箙鍖栥€佹枃妗ｄ笂浼犺В鏋愩€佸叧閿瘝妫€绱€佽瘖鏂€丼OP銆佷换鍔°€佽褰曚腑蹇冦€佸獟浣撳拰鐭ヨ瘑鍥捐氨鑳藉姏锛涙湰鍦?8010 鍚庣鍋ュ悍妫€鏌ュ拰绯荤粺鐘舵€佸彲鐢紝鏁版嵁搴撶姸鎬佷负 `online`銆?- 澶氭櫤鑳戒綋娴佺▼锛欰gent Runtime銆佸伐鍏疯皟鐢ㄣ€佸鎵广€乤rtifact 鍜屾樉寮忚浆鎹㈡祦绋嬪凡缁忓叿澶囧伐绋嬮鏋讹紝骞惰兘閫氳繃 dry-run / mock-run 鏂瑰紡灞曠ず涓氬姟閾捐矾锛涗絾浠嶄笉鏄嚜娌荤敓浜ф櫤鑳戒綋锛屾寮忓璞″垱寤轰緷璧栦汉宸ュ鎵瑰拰鏄惧紡杞崲銆?- 鐪熷疄澶栭儴 API锛歁odel Gateway 涓?cloud/local provider 瀛樺湪鐪熷疄 HTTP 璋冪敤璺緞锛屼絾褰撳墠鏈湴閰嶇疆鏈惎鐢ㄧ湡瀹炰簯绔?鏈湴妯″瀷锛汦xternal API Provider Gateway 褰撳墠涓昏鏄厤缃€佽劚鏁忋€乨ry-run銆乵ock-run 鍜?blocked 鎺ュ叆浣嶏紝涓嶆槸瀹屾暣 real-call 缃戝叧銆?- 浼佷笟绾?RAG锛氬綋鍓嶆槸 PostgreSQL 鍏抽敭璇嶆绱?+ 涓枃鍏抽敭璇嶆墿灞?+ 瑙勫垯璇勫垎 + KG 澧炲己锛屼笉鏄?embedding / pgvector / hybrid retrieval / rerank 鐨勪紒涓氱骇鍚戦噺 RAG銆?- 瀹夊叏鍚堣锛氬熀纭€ JWT銆丷BAC銆佷笂浼犺矾寰勬牎楠屻€佸閮?API 鏃ュ織鑴辨晱宸叉湁锛涗絾鐢熶骇瀵嗛挜銆侀粯璁ょ鍙ｃ€丆ORS銆乺ate limit銆佸璁＄暀瀛樸€佹晱鎰熸棩蹇楃瓥鐣ュ拰 `.env` 鐢熶骇妫€鏌ヤ粛闇€鍔犲浐銆?- 榫欒姱 / 楹掗簾閮ㄧ讲锛氭枃妗ｅ拰鑴氭湰璺嚎瀹屾暣锛岀鍚?Python venv + native PostgreSQL + systemd + Nginx锛涗絾褰撳墠鍙槸 Windows 鏈満楠岃瘉锛屼笉鏄?LoongArch/Kylin 瀹炴満閫氳繃銆?- 鐢熶骇浜や粯鎴愮啛搴︼細褰撳墠灞炰簬鈥滃姛鑳介棴鐜拰楂樼骇鎺ュ叆浣嶈緝瀹屾暣銆佸彲婕旂ず锛屼絾浠嶉渶瀹夊叏銆丷AG銆佺湡瀹?API銆佸苟鍙戙€佹€ц兘銆佸疄鏈洪儴缃插拰浜や粯娓呯悊鍔犲浐鈥濈殑闃舵銆?
## 3. 宸茶揪鍒伴珮鏍囧噯鐨勯儴鍒?
### 3.1 鑼冨洿鏀舵暃

- 绗竴鐗堣寖鍥村凡鏄庣‘鑱氱劍鍗庝负銆侀槼鍏夌數婧愩€佸厜浼忛€嗗彉鍣ㄣ€?- 鏂囨。鍜屽墠绔富绾挎湭灏嗗偍鑳姐€佺鍙樸€侀€氱敤鏈哄櫒浜烘垨杞﹁締缁翠慨浣滀负绗竴鐗堜富鑼冨洿銆?
### 3.2 鍚庣鍒嗗眰

- 鍚庣鏁翠綋閬靛惊 `api -> service -> repository -> model`銆?- 涓昏鍐欎笟鍔℃帴鍙ｉ€氳繃 service 灞傜粍缁囥€?- 妯″瀷闆嗕腑浜?SQLAlchemy models锛屽苟绾冲叆 Alembic metadata銆?
### 3.3 PostgreSQL 涓?Alembic

- Alembic 褰撳墠鐗堟湰涓?`20260601_0006 (head)`銆?- `alembic heads` 浠呮樉绀轰竴涓?head锛歚20260601_0006 (head)`銆?- 褰撳墠鍚庣 `/api/system/status` 鎶ュ憡鏁版嵁搴撶姸鎬佷负 `online`銆?- 杩佺Щ閾惧寘鍚牳蹇冭〃銆佺煡璇嗗浘璋便€丄gent Runtime銆丒xternal API Provider Gateway銆佸妯℃€佽瘉鎹腑蹇冦€?
### 3.4 API 涓庡墠绔瀯寤?
- 8010 涓?OpenAPI title 涓?`Energy-Maintenance`锛岃矾寰勬暟閲忎负 135銆?- 鏍稿績 API 鍖呮嫭锛氳璇併€佽澶囥€佺煡璇嗗簱銆佹绱€佽瘖鏂€丼OP銆佷换鍔°€佽褰曚腑蹇冦€佸獟浣撱€佺煡璇嗗浘璋便€佹ā鍨嬬綉鍏炽€佸閮?API銆丄gent銆佸妯℃€併€?- `npm.cmd run build` 閫氳繃銆?
### 3.5 涓婁紶瀹夊叏鍩虹

- 濯掍綋涓婁紶鏈嶅姟涓彲瑙佹枃浠跺悕鍑€鍖栥€佹墿灞曞悕妫€鏌ャ€佸ぇ灏忛檺鍒躲€佷笂浼犵洰褰曚笉鍦?frontend 涓嬨€佽矾寰勫繀椤讳綅浜庝笂浼犵洰褰曞唴绛夐槻鎶ゃ€?- 鐭ヨ瘑搴撴枃妗ｄ笂浼犲拰濯掍綋涓婁紶鍧囨病鏈夋妸鍓嶇鐩綍浣滀负瀛樺偍璺緞銆?
### 3.6 澶栭儴 API 鑴辨晱鍩虹

- `ExternalApiSanitizer` 瀵?API key銆乤uthorization銆乼oken銆乻ecret銆乸assword銆乥ase64銆乥inary 绛夊瓧娈靛仛鑴辨晱銆?- 澶栭儴 API 鏃ュ織鏋勫缓浣跨敤 sanitized request/response summary銆?- Provider status 鏆撮湶鐨勬槸 `api_key_configured` 鍜?masked URL/key 绛夊畨鍏ㄥ厓鏁版嵁锛岃€屼笉鏄槑鏂?Key銆?
### 3.7 楂橀闄╁姩浣滆竟鐣?
- Agent 宸ュ叿鏀寔 blocked銆亀aiting_approval銆乺equires_approval銆?- task draft銆乲nowledge contribution draft銆乧orrection draft 绛夐珮椋庨櫓鍐欏姩浣滈粯璁ょ敓鎴愯崏绋垮拰瀹℃壒锛屼笉鐩存帴鍙樻垚姝ｅ紡瀵硅薄銆?- 22J 鐨?artifact conversion 闇€瑕?expert/admin 鏄惧紡瑙﹀彂锛屼笉鍥?approval 鑷姩杞崲銆?
## 4. 涓嶈揪鏍囨垨闇€鎻愰珮鐨勯儴鍒?
### P0-1锛氬綋鍓嶅伐浣滄爲涓嶉€傚悎鐩存帴浜や粯鎴栨墦鍖?
- evidence锛歚git status --short` 鏄剧ず澶ч噺淇敼銆佸垹闄ゅ拰鏈窡韪枃浠讹紱鍖呮嫭 22A-22J 鐩稿叧鏂板浠ｇ爜鍜屾枃妗ｃ€侀潤鎬佸墠绔瀯寤轰骇鐗╁彉鍖栵紝浠ュ強鏈窡韪?`docs.zip`銆?- risk锛氫氦浠樺寘鎴?commit 鍙兘娣峰叆鏈鏍告枃浠躲€佹棫鏋勫缓浜х墿銆佷复鏃跺帇缂╁寘鎴栬法浠诲姟閬楃暀鍐呭銆?- recommended fix锛氬湪 24B 涔嬪墠涓嶈鎵撳寘锛涘厛鎵ц涓撻棬鐨勪氦浠樻竻鐞嗕换鍔★紝鍖哄垎搴旂撼鍏ョ増鏈殑 22A-22J 鏂囦欢銆佸簲蹇界暐鐨勯潤鎬佹棫 hash 鏂囦欢銆佸簲鍒犻櫎鎴栫Щ鍔ㄧ殑涓存椂 `docs.zip`銆?
### P0-2锛氱敓浜у瘑閽ヤ笌鏈湴 `.env` 浠嶆槸寮€鍙戞€?
- evidence锛歚.env` key 鐘舵€佹鏌ユ樉绀?`SECRET_KEY` 灞炰簬 dev/placeholder 绫荤姸鎬侊紱澶氫釜澶栭儴 API Key 涓哄崰浣嶆垨绌哄€硷紱`.env` 琚?gitignore 蹇界暐锛屾湭杈撳嚭浠讳綍鏄庢枃鍊笺€?- risk锛氬鏋滆鐢ㄥ紑鍙戝瘑閽ユ垨榛樿瀵嗙爜涓婄嚎锛屼細瀵艰嚧 JWT銆佸悗鍙拌处鍙枫€佸閮?provider 閰嶇疆瀛樺湪瀹夊叏椋庨櫓銆?- recommended fix锛?4D 澧炲姞鐢熶骇鍚姩纭牎楠岋細鐢熶骇鐜绂佹 dev SECRET_KEY锛涜姹?ADMIN_PASSWORD 鎴栫鐞嗗憳鍒濆鍖栨祦绋嬶紱绂佹鍗犱綅绗?API Key 琚垽瀹氫负 configured銆?
### P0-3锛氱湡瀹炲閮?API銆丱CR銆丮IMO銆丩oongArch/Kylin 涓嶅彲鍦ㄦ姤鍛婁腑鍐欐垚宸查€氳繃

- evidence锛欵xternal API adapters 杩斿洖 `real_external_call_disabled`銆乣future_real_invoke_entry`銆乣would_call`銆乣blocked`锛涘妯℃€佹湇鍔″尯鍒?dry-run / mock-run锛汱oongArch/Kylin 鑴氭湰鍙槸鍙鐜妫€鏌ワ紱褰撳墠楠岃瘉鍦?Windows 鏈満瀹屾垚銆?- risk锛氱瓟杈╂垨浜や粯鎶ュ憡鑻ュ啓鈥滅湡瀹?MIMO 宸叉帴閫?/ OCR 宸茶瘑鍒?/ 榫欒姱瀹炴満宸查儴缃测€濓紝浼氭瀯鎴愯兘鍔涘じ澶с€?- recommended fix锛氭姤鍛婃潗鏂欑粺涓€鐢ㄢ€滈鐣欍€乨ry-run銆乵ock-run銆乥locked銆佸緟瀹炴満楠屾敹鈥濊〃杩般€?
### P0-4锛歅ostgreSQL Windows service 鏈ǔ瀹氬寲

- evidence锛歚postgresql-x64-16` 鏈嶅姟鐘舵€佷负 `Stopped`锛孲tartType 涓?`Disabled`锛涘綋鍓嶅彲鐢ㄦ暟鎹簱绔彛鏄?55432锛?432 琚叾浠栬繘绋嬪崰鐢ㄣ€?- risk锛氶噸鍚悗绯荤粺涓嶈兘鑷姩鎭㈠锛涘紑鍙戝拰婕旂ず渚濊禆 standalone postgres.exe 鎴栦复鏃剁鍙ｏ紝绋冲畾鎬т笉瓒炽€?- recommended fix锛氬湪 Windows 寮€鍙戠幆澧冧慨澶嶅師鐢?PostgreSQL service锛屾垨鏄庣‘ 55432 涓烘湰鏈轰复鏃堕厤缃紱鐢熶骇鐜蹇呴』浣跨敤 systemd/native service銆?
### P1-1锛氫紒涓氱骇鍚戦噺 RAG 灏氭湭瀹炵幇

- evidence锛氫唬鐮佷腑鍙湁 `embedding_status` 棰勭暀瀛楁鍜屾枃妗ｄ腑鐨?pgvector/embedding 鍚庣画璺嚎锛涙湭鍙戠幇 pgvector 鎵╁睍銆佸悜閲忓瓧娈点€乪mbedding service銆乹uery embedding銆乧hunk embedding銆乭ybrid retrieval 鎴?reranker 瀹炵幇銆?- risk锛氶潰瀵瑰ぇ瑙勬ā鏂囨。鍜岃涔夋ā绯婃煡璇㈡椂鍙洖璐ㄩ噺銆佹帓搴忚川閲忓拰鍙瘎浼版€т笉瓒炽€?- recommended fix锛歍ask 24B 鎺ュ叆 pgvector + embedding + hybrid retrieval + rerank + 璇勪及闆嗐€?
### P1-2锛欵xternal API Provider Gateway 浠呴厤缃?`.env` 涓嶈冻浠ョ湡瀹炲鍛?
- evidence锛欵xternal API adapters 鐨?`invoke` 閫昏緫浠嶈繑鍥?blocked/would_call锛宮essage 鏄庣‘鈥滀笉鐪熷疄澶栧懠鈥濓紱MIMO/OCR/OpenAI-compatible adapters 鍙繚鐣?request builder 鍜?future real invoke entry銆?- risk锛氱敤鎴峰～浜?MIMO 鎴?OCR 閰嶇疆鍚庝粛涓嶈兘閫氳繃 Provider Gateway 寰楀埌鐪熷疄缁撴灉銆?- recommended fix锛歍ask 24C 涓?MIMO銆丆loud Vision銆丱CR API銆丱penAI-compatible chat 鍒嗗埆琛?real-run adapter銆佽秴鏃躲€侀噸璇曘€侀檺娴併€佹棩蹇楄劚鏁忋€佸け璐ュ洖閫€銆?
### P1-3锛氬妯℃€佽瘉鎹腑蹇冪湡瀹炶瘑鍒摼璺笉瓒?
- evidence锛氬妯℃€侀〉闈㈠拰鏈嶅姟鏄庣‘浣跨敤 dry-run/mock-run锛沵ock-run 浼氱敓鎴愭ā鎷?OCR/AI 缁撴灉锛宺eal OCR/MIMO 涓嶉粯璁ゅ惎鐢ㄣ€?- risk锛氬浘鐗囪瘉鎹彧鑳戒綔涓轰汉宸ヤ笂浼犲拰妯℃嫙婕旂ず锛屼笉瓒充互鏀拺鐪熷疄鐜板満鍥剧墖璇嗗埆銆?- recommended fix锛歍ask 24C/24G 澧炲姞鐪熷疄 OCR/MIMO 璋冪敤銆佺粨鏋滀汉宸ュ鏍搞€乤ccepted 缁撴灉杩涘叆璇婃柇/SOP/鐭ヨ瘑娌夋穩鐨勭湡瀹為棴鐜€?
### P1-4锛欰gent artifact conversion 闃查噸澶嶄緷璧?event log锛岀己灏戠嫭绔嬭浆鎹㈣〃鍜屾暟鎹簱鍞竴绾︽潫

- evidence锛氳浆鎹㈤€昏緫閫氳繃 `find_conversion_event` 妫€鏌ラ噸澶嶏紝骞跺啓鍏?`agent_event_logs`锛涙病鏈夌嫭绔?`agent_artifact_conversions` 琛ㄣ€?- risk锛氬苟鍙戝弻鍑汇€佸苟鍙戣姹傛垨浜嬪姟绔炴€佷笅鍙兘閲嶅鍒涘缓姝ｅ紡瀵硅薄锛涙煡璇㈠拰瀹¤涔熶緷璧?JSON event payload銆?- recommended fix锛歍ask 24E 鏂板 `agent_artifact_conversions` 琛紝璁剧疆 `(source_artifact_id, target_type)` 鍞竴绾︽潫銆佽浆鎹㈢姸鎬併€佸け璐ュ師鍥犮€佹挙閿€/浣滃簾瀛楁銆?
### P1-5锛氶儴鍒嗘祴璇曡剼鏈粯璁ょ鍙ｄ粛鏄?8000/5432

- evidence锛歚final_smoke_test.ps1` 榛樿 8000锛涢儴鍒嗘棭鏈?check 鑴氭湰榛樿 `http://127.0.0.1:8000/api`锛沇indows PostgreSQL 妫€鏌ヨ剼鏈粯璁?5432銆?- risk锛氭湰鏈哄椤圭洰鐜涓?8000/5432 宸茶鍏朵粬椤圭洰鍗犵敤锛屽彲鑳借娴嬪叾浠栭」鐩垨璇姤澶辫触銆?- recommended fix锛氱粺涓€鑴氭湰榛樿璇诲彇 `.env` / `BASE_URL` / `DATABASE_URL`锛屽苟鍦ㄦ姤鍛婁腑鏄惧紡瑕佹眰 8010/55432 浠呬负鏈満涓存椂绔彛銆?
### P1-6锛氬畨鍏ㄨ兘鍔涚己灏?rate limit銆佽姹備綋鍏ㄥ眬闄愬埗鍜岀郴缁熸€ц秺鏉冩祴璇?
- evidence锛氬凡鏈?HTTPBearer/JWT/RBAC锛屼絾鏈缁熶竴 rate limiter銆佷腑闂翠欢绾ц姹備綋澶у皬闄愬埗銆丆SRF 绛栫暐鎴栫郴缁熸€?RBAC 鐭╅樀娴嬭瘯瑕嗙洊鎵€鏈夋柊澧?Agent/External API/Multimodal 鍐欐帴鍙ｃ€?- risk锛氫紒涓氱幆澧冧笅鏄撳彈鏆村姏鐧诲綍銆佸ぇ璇锋眰婊ョ敤銆佽秺鏉冭竟鐣岄仐婕忓奖鍝嶃€?- recommended fix锛歍ask 24D 澧炲姞鐧诲綍/鍐欐帴鍙ｉ檺娴併€佽姹備綋澶у皬闄愬埗銆丷BAC 鑷姩鍖栨祴璇曠煩闃点€佸畨鍏ㄦ棩蹇楃瓥鐣ャ€?
### P1-7锛氭€ц兘涓庡苟鍙戞祴璇曚笉瓒?
- evidence锛氱幇鏈夎剼鏈涓?smoke銆乫low銆乥rowser 鐐瑰嚮銆乥locked/fallback 楠岃瘉锛涙湭瑙佸苟鍙戜笂浼犮€佸苟鍙戞绱€佸苟鍙戣浆鎹€佸ぇ鏂囨。鎵归噺瑙ｆ瀽銆並G 澶у浘鎬ц兘娴嬭瘯銆?- risk锛氭紨绀烘暟鎹妯″彲鐢ㄤ笉浠ｈ〃浼佷笟瑙勬ā鍙敤銆?- recommended fix锛氬鍔犳绱?QPS銆佷笂浼犺В鏋愬帇鍔涖€佸苟鍙戣浆鎹€佹棩蹇楄〃鑶ㄨ儉銆佸垎椤垫€ц兘娴嬭瘯銆?
### P2-1锛氬墠绔粛鏈夋妧鏈€佽嫳鏂囧拰澶嶆潅椤甸潰鍙鎬ч棶棰?
- evidence锛氬墠绔繚鐣?`mock-run`銆乣dry-run`銆乣provider` 绛夋妧鏈湳璇紱Agent Workbench銆佸妯℃€侀〉闈㈡壙杞借緝澶氱姸鎬佸拰 JSON 缁撴灉銆?- risk锛氭櫘閫氳繍缁翠汉鍛樼悊瑙ｆ垚鏈緝楂樸€?- recommended fix锛氱户缁仛鈥滄妧鏈瓧娈典繚鐣?+ 鐢ㄦ埛涓绘爣棰樹腑鏂囧寲 + 灞曞紑寮忔妧鏈鎯呪€濈殑 UI 浼樺寲銆?
### P2-2锛欽SONB 浣跨敤骞挎硾浣嗙己灏?GIN / 琛ㄨ揪寮忕储寮曠瓥鐣?
- evidence锛氬ぇ閲忔ā鍨嬩娇鐢?JSONB锛屼緥濡?record銆乤gent銆乪xternal_api銆乵ultimodal銆乲nowledge_graph锛涜縼绉讳腑涓昏鏄櫘閫?BTree 绱㈠紩锛屾湭绯荤粺鎬у鍔?JSONB GIN 绱㈠紩銆?- risk锛氬悗鏈熸寜 JSONB 鍐呭瓧娈垫绱€佺粺璁°€佸璁′細鍙樻參銆?- recommended fix锛氬熀浜庣湡瀹炴煡璇㈡ā寮忓喅瀹?GIN/琛ㄨ揪寮忕储寮曪紝閬垮厤鐩茬洰鍔犵储寮曘€?
### P2-3锛氭棩蹇楀拰瀹¤琛ㄥ闀跨瓥鐣ヤ笉瓒?
- evidence锛歚operation_logs`銆乣model_call_logs`銆乣agent_event_logs`銆乣external_api_call_logs` 鍧囧彲鎸佺画澧為暱銆?- risk锛氶暱鏈熻繍琛屽悗鏁版嵁搴撹啫鑳€锛屽浠藉拰鏌ヨ鍙樻參銆?- recommended fix锛氬鍔犳棩蹇楃暀瀛樼瓥鐣ャ€佸綊妗ｄ换鍔°€佹寜鏃堕棿鍒嗗尯鎴栧畾鏈熸竻鐞嗚鍒欍€?
## 5. RAG 涓撻」瀹℃煡

褰撳墠瀹屾垚锛?
- PostgreSQL 涓繚瀛?`knowledge_documents` 鍜?`knowledge_chunks`銆?- 鏀寔鏂囨。涓婁紶銆佽В鏋愩€佹竻娲椼€佸垏鐗囥€佸叆搴撱€?- 妫€绱㈡湇鍔″熀浜庡叧閿瘝銆佷腑鏂囧叧閿瘝鎵╁睍銆佷笟鍔″瓧娈靛尮閰嶅拰瑙勫垯璇勫垎銆?- references 鏉ヨ嚜鐪熷疄 chunk/document锛孮A 璁板綍淇濆瓨鍒?`qa_records`銆?- 鏀寔 KG context銆佸獟浣?OCR context 浣滀负澧炲己杈撳叆锛屼絾涓嶆槸鍚戦噺璇箟妫€绱€?
缂哄皯鍐呭锛?
- 娌℃湁 embedding service銆?- 娌℃湁 embedding 妯″瀷閰嶇疆銆?- 娌℃湁 pgvector extension銆?- 娌℃湁 vector 绫诲瀷瀛楁鎴栫嫭绔嬪悜閲忚〃銆?- 娌℃湁 query embedding / chunk embedding銆?- 娌℃湁鍚戦噺鍙洖銆?- 娌℃湁 keyword + vector hybrid retrieval銆?- 娌℃湁 rerank銆?- 娌℃湁 RAG 璇勪及闆嗐€佸彫鍥炵巼銆佸噯纭巼銆佸懡涓巼娴嬭瘯銆?- `knowledge_curator_agent` 鐨?duplicate risk 鏇村亸瑙勫垯/鍏抽敭璇?涓婁笅鏂囧垽鏂紝涓嶆槸璇箟閲嶅妫€娴嬨€?
闇€瑕佽ˉ榻愶細

- Task 24B锛氫负 `knowledge_chunks` 澧炲姞 embedding 瀛楁鎴栫嫭绔?embedding 琛ㄣ€?- 澧炲姞 pgvector migration 鍜?PostgreSQL extension 妫€鏌ャ€?- 澧炲姞 CPU-friendly embedding provider锛岄伩鍏?LoongArch 涓婂己鍒?GPU銆?- 澧炲姞鍏抽敭璇嶅彫鍥?+ 鍚戦噺鍙洖 + 瑙勫垯閲嶆帓鐨?hybrid pipeline銆?- 澧炲姞 retrieval evaluation dataset 鍜屾寚鏍囨姤鍛娿€?
## 6. 鐪熷疄 API 涓撻」瀹℃煡

### MIMO

- 褰撳墠锛欵xternal API Provider Gateway 涓湁 `mimo_2_5` provider 鍜?route锛孧IMO adapter 鏋勯€犺劚鏁忚姹傚苟杩斿洖 blocked/would_call锛屼笉鐪熷疄澶栧懠銆?- 浠呭～ `.env` 鏄惁瓒冲锛氫笉瓒炽€傞渶瑕佽ˉ `MimoMultimodalAdapter` real-run銆?- 闇€琛ユ枃浠讹細`external_api_adapters/mimo_multimodal_adapter.py`銆乣external_api_gateway.py`銆佸妯℃€佺粨鏋?normalizer銆侀獙鏀惰剼鏈€?
### CLOUD_LLM

- 褰撳墠锛歁odel Gateway 鐨?`cloud_openai_adapter.py` 鏈夌湡瀹?HTTP chat call 璺緞锛屽彈 `CLOUD_LLM_ENABLED` 鍜岄厤缃帶鍒讹紱External API Provider Gateway 鐨?`cloud_openai` 璺敱浠嶆槸 dry-run/blocked 璇箟銆?- 浠呭～ `.env` 鏄惁瓒冲锛氬鏃?Model Gateway chat 璺緞鍙兘瓒冲锛涘 External API Provider Gateway 涓嶈冻銆?- 闇€琛ユ枃浠讹細`external_api_adapters/openai_compatible_adapter.py` real-run锛岀粺涓€ Model Gateway 涓?External API Gateway 杈圭晫銆?
### CLOUD_VISION

- 褰撳墠锛歅rovider 鍜?route 棰勭暀锛屾湭瑙佺湡瀹?vision call銆?- 浠呭～ `.env` 鏄惁瓒冲锛氫笉瓒炽€?- 闇€琛ユ枃浠讹細vision request builder銆丱penAI-compatible vision adapter銆乺esponse parser銆乵edia AI analysis writer銆?
### OCR_API

- 褰撳墠锛歚OCR_API` provider 棰勭暀锛汷CR API adapter 涓嶇湡瀹炲鍛笺€?- 浠呭～ `.env` 鏄惁瓒冲锛氫笉瓒炽€?- 闇€琛ユ枃浠讹細`ocr_api_adapter.py` real-run銆丱CR result normalizer銆侀敊璇鐞嗗拰鏃ュ織鑴辨晱銆?
### LOCAL_LLM

- 褰撳墠锛歁odel Gateway 涓?`local_llama_cpp_adapter.py` 鏈?HTTP call 璺緞锛涢渶瑕佹湰鍦?llama.cpp 鏈嶅姟銆侲xternal API Provider Gateway 鐨?local provider浠嶅亸閰嶇疆/璺敱棰勭暀銆?- 浠呭～ `.env` 鏄惁瓒冲锛氬彧鏈夊湪鏈湴 llama.cpp 鏈嶅姟鐪熷疄杩愯鏃舵墠鍙兘瓒冲锛涗笉鑳戒綔涓烘牳蹇冨繀闇€椤广€?
## 7. 澶氭ā鎬佷笓椤瑰鏌?
褰撳墠鑳藉姏锛?
- `media_processing_jobs` 璁板綍澶勭悊浠诲姟銆?- `media_ocr_results`銆乣media_ai_analyses`銆乣media_evidence_links` 鏀寔缁撴灉銆佸鏍稿拰璇佹嵁閾炬帴銆?- 椤甸潰鍜屽悗绔槑纭尯鍒?dry-run銆乵ock-run銆乥locked銆乤ccepted/pending/rejected銆?- mock-run 鍙厑璁?admin/expert銆?- 濯掍綋鏂囦欢涓婁紶鏈夊畨鍏ㄦ鏌ュ拰閴存潈銆?
缂哄彛锛?
- OCR 鐪熷疄璇嗗埆榛樿 disabled銆?- MIMO / Cloud Vision 涓嶇湡瀹炶皟鐢ㄣ€?- mock-run 鑳界敓鎴愭ā鎷熺粨鏋滐紝蹇呴』鍦ㄦ姤鍛婂拰 UI 涓槑纭ā鎷熸€ц川銆?- 澶у浘銆佸潖鍥俱€侀潪鍥剧墖鐨勭湡瀹?OCR/瑙嗚閿欒澶勭悊浠嶉渶鐪熷疄楠屾敹銆?- accepted 缁撴灉杩涘叆璇婃柇/SOP/鐭ヨ瘑娌夋穩鐨勭湡瀹炵敓浜ц川閲忎粛闇€鏇翠弗鏍兼祴璇曘€?
CPU-only / LoongArch 椋庨櫓锛?
- 鏈湴 OCR/Tesseract銆乴lama.cpp銆佹ā鍨嬭繍琛屾椂閮戒緷璧栫洰鏍囨満浜岃繘鍒跺拰璇█鍖呫€?- 涓嶅簲鎶婁换浣曟湰鍦板ぇ妯″瀷鎴?OCR 寮曟搸鍒椾负绗竴鐗堝繀闇€渚濊禆銆?
## 8. 澶氭櫤鑳戒綋涓撻」瀹℃煡

### multimodal_evidence_agent

- 瀹屾垚搴︼細鏈?orchestrator锛岄粯璁ゅ伐鍏蜂负 media lookup銆丱CR銆丮IMO analysis銆乻afety guard锛涘彲鐢熸垚 evidence summary銆乻afety checklist銆乼race artifact銆?- 椋庨櫓锛氱湡瀹?OCR/MIMO blocked锛沵ocked 璇佹嵁闇€鏄庣‘杈圭晫锛涘鐪熷疄鍥剧墖鐞嗚В鑳藉姏涓嶈兘澶稿ぇ銆?
### fault_diagnosis_agent

- 瀹屾垚搴︼細鏈夎瘖鏂紪鎺掋€佺煡璇嗘绱€佽澶?璁板綍/KG/瀹夊叏涓婁笅鏂囷紝鐢熸垚璇婃柇鎽樿鍜屽畨鍏?artifact銆?- 椋庨櫓锛氫笉璋冪敤鐪熷疄 LLM銆乪mbedding 鎴?pgvector锛涜瘖鏂粛鏄鍒?妫€绱㈣緟鍔╋紝涓嶆槸纭畾鎬ф晠闅滃垽鏂€?
### sop_planner_agent

- 瀹屾垚搴︼細鐢熸垚 SOP draft銆乻afety checklist銆乼race artifact銆?- 椋庨櫓锛氫笉鑳借嚜鍔ㄧ敓鎴愭寮?SOP execution锛涢渶瑕佷汉宸ュ鏍稿拰鍚庣画杞崲銆?
### task_orchestration_agent

- 瀹屾垚搴︼細鐢熸垚 task_draft锛屼笉鑷姩鍒涘缓銆佸垎娲俱€佸紑宸ユ垨瀹屾垚姝ｅ紡浠诲姟銆?- 椋庨櫓锛氶渶瑕佽浆鎹㈣〃闃插苟鍙戦噸澶嶏紱鐪熷疄璋冨害娴佺▼浠嶈浜哄伐纭銆?
### knowledge_curator_agent

- 瀹屾垚搴︼細鐢熸垚 maintenance_case_summary銆乲nowledge_contribution_draft銆乲g_candidate_suggestion銆乻afety_checklist銆乼race銆?- 椋庨櫓锛氫笉鑷姩鍒涘缓姝ｅ紡 contribution/document/chunks/KG nodes锛沝uplicate risk 涓嶆槸 embedding 璇箟鏌ラ噸銆?
### 22J 鑽夌杞崲

- 瀹屾垚搴︼細approval 涓嶈嚜鍔ㄨ浆鎹紝expert/admin 鏄惧紡 convert锛涙敮鎸?knowledge_contribution銆乻op_template銆乵aintenance_task銆乲g_candidate銆?- 椋庨櫓锛氶噸澶嶈浆鎹緷璧?event log 鏌ヨ锛岀己灏戠嫭绔嬭浆鎹㈣〃鍜屽敮涓€绾︽潫锛涚己灏戞挙閿€/浣滃簾娴佺▼锛涘け璐ュ璁″拰鍓嶇鐘舵€佸彲浠ョ户缁寮恒€?
## 9. 鑽夌杞崲涓撻」瀹℃煡

宸插畬鎴愶細

- 瀹℃壒閫氳繃涓嶈嚜鍔ㄨ浆鎹€?- 杞崲蹇呴』 expert/admin 鏄惧紡瑙﹀彂銆?- 杞崲鍐欏璁′簨浠讹紝骞惰繑鍥?conversion trace銆?- 楂橀闄?mock/unreviewed evidence 瀵?expert 榛樿闃绘柇锛宎dmin 鍙?override銆?
涓昏椋庨櫓锛?
- 閲嶅杞崲鍙潬 `agent_event_logs` 涓?JSON payload 鏌ユ壘锛岀己灏戞暟鎹簱鍞竴绾︽潫銆?- 骞跺彂璇锋眰鍙兘缁曡繃搴旂敤灞?duplicate check銆?- 娌℃湁 `agent_artifact_conversions` 鐙珛琛紝鏌ヨ銆佺粺璁°€佹挙閿€銆佸け璐ラ噸璇曢兘涓嶅浼佷笟鍖栥€?- 缂哄皯姝ｅ紡鎾ら攢 / 浣滃簾 / 鍥炴粴涓氬姟瀵硅薄鏈哄埗銆?
寤鸿锛?
- Task 24E 鏂板 conversion 琛ㄥ拰鍞竴绾︽潫銆?- 杞崲杩囩▼缁熶竴 transaction boundary銆?- 澧炲姞鍓嶇杞崲鍘嗗彶銆佸け璐ュ師鍥犮€佷笉鍙噸澶嶆彁绀哄拰浣滃簾鍏ュ彛銆?
## 10. 瀹夊叏涓撻」瀹℃煡

褰撳墠宸叉湁锛?
- JWT bearer 閴存潈銆?- 鍚庣 `require_roles` 鍜?`require_admin`銆?- 鍓嶇 router roles 鍜屾寜閽彲瑙佹€с€?- 涓婁紶鐩綍鍜屾枃浠跺悕瀹夊叏澶勭悊銆?- External API request/response 鏃ュ織鑴辨晱銆?- `.env` 琚?gitignore 蹇界暐銆?
椋庨櫓鍜岀己鍙ｏ細

- 鏈湴 `.env` 浠嶆槸寮€鍙戞€侊紝`SECRET_KEY` 涓?dev/placeholder 绫荤姸鎬併€?- `backend/app/core/config.py` 涓粯璁?`DATABASE_URL` 鍖呭惈绀轰緥璐﹀彿瀵嗙爜锛岀敓浜ч儴缃查渶瑕佸己鍒剁敱鐜鍙橀噺瑕嗙洊銆?- CORS 褰撳墠閫傞厤鏈湴寮€鍙戯紝鐢熶骇鐜闇€鏀舵暃銆?- 鏈缁熶竴 rate limit銆?- 鏈鍏ㄥ眬璇锋眰浣撳ぇ灏忛檺鍒躲€?- 鏈 CSRF 绛栫暐璇存槑锛涜嫢鍙蛋 Bearer API 椋庨櫓杈冧綆锛屼絾浠嶉渶鏂囨。鍖栥€?- RBAC 瑕嗙洊杈冨锛屼絾鏂板 Agent/External API/Multimodal 鐨勫叏鐭╅樀瓒婃潈娴嬭瘯杩橀渶瑕佺户缁帇瀹炪€?- `model_call_logs`銆乣external_api_call_logs`銆乣agent_event_logs` 闇€瑕佹棩蹇楃暀瀛樺拰鏁忔劅瀛楁浜屾瀹¤銆?- 鏂囨。涓湁绀轰緥鏁版嵁搴撳瘑鐮侊紝閫傚悎浣滀负鏈湴绀轰緥锛屼笉搴斿嚭鐜板湪鐢熶骇閮ㄧ讲鏉愭枡鐨勨€滅湡瀹為厤缃€濅腑銆?
## 11. 榫欒姱 / 楹掗簾閮ㄧ讲涓撻」瀹℃煡

褰撳墠绗﹀悎鐐癸細

- 姝ｅ紡璺嚎鏄庣‘涓?LoongArch + Kylin + Python venv + native PostgreSQL + systemd + Nginx銆?- 鏂囨。绂佹 Docker 鍜?SQLite 浣滀负姝ｅ紡璺嚎銆?- `scripts/check_loongarch_kylin.sh` 涓哄彧璇绘鏌ヨ剼鏈紝涓嶅畨瑁呫€佷笉杩佺Щ銆佷笉鏀规湇鍔°€?- 鏈湴 llama.cpp/GGUF 鍜?Tesseract OCR 閮借鏍囦负鍙€夎兘鍔涖€?
缂哄彛锛?
- 褰撳墠楠岃瘉鍦?Windows 鏈満锛屼笉鑳界瓑鍚?LoongArch/Kylin 瀹炴満楠屾敹銆?- 鏈鐩爣鏈哄疄闄呭畨瑁呫€佽縼绉汇€佸惎鍔ㄣ€丯ginx銆乻ystemd銆佷笂浼犵洰褰曟潈闄愩€佸浠芥仮澶嶇殑瀹炴満鏃ュ織銆?- OCR銆乴lama.cpp銆丯ode銆乽v 鍦?LoongArch 涓婄殑鍙敤鎬т粛闇€瀹炴満楠岃瘉銆?- PostgreSQL Windows service 褰撳墠 disabled/stopped锛岃櫧鐒朵笉褰卞搷 Linux systemd 璺嚎锛屼絾璇存槑鏈満婕旂ず鎭㈠鑳藉姏涓嶈冻銆?
寤鸿锛?
- Task 24F 鍦ㄧ湡瀹?LoongArch/Kylin 鐜杩愯 `scripts/check_loongarch_kylin.sh`銆?- 鍦ㄧ洰鏍囨満鎵ц PostgreSQL 鍒濆鍖栥€丄lembic migration銆佸悗绔?systemd銆丯ginx銆侀潤鎬佸墠绔€佷笂浼犲拰妫€绱㈤棴鐜€?- 鏈湴妯″瀷/OCR 浣滀负鍙€夐獙鏀堕」鍗曠嫭璁板綍銆?
## 12. 娴嬭瘯涓撻」瀹℃煡

宸叉湁娴嬭瘯绫诲瀷锛?
- smoke锛歚scripts/final_smoke_test.ps1`
- global acceptance锛歚backend/scripts/check_global_acceptance.py`
- 鍓嶇 API 鎺ュ叆锛歚check_real_frontend_api_integration.py`
- 娴忚鍣ㄧ偣鍑伙細`check_task21c_browser_clicks.mjs`
- destructive action/cleanup锛歚check_task21d_destructive_actions.py`
- External API Gateway dry-run锛歚check_external_api_gateway_flow.py`
- Multimodal evidence flow锛歚check_multimodal_evidence_flow.py`
- Adapter contract锛歚check_multimodal_adapter_contract.py`
- Agent flows锛歚check_agent_runtime_flow.py`銆乣check_agent_business_tools_flow.py`銆乣check_multimodal_evidence_agent_flow.py`銆乣check_diagnosis_sop_task_agent_flow.py`銆乣check_knowledge_curator_agent_flow.py`銆乣check_agent_artifact_conversion_flow.py`
- Browser Agent checks锛歚check_task22f_*` 鍒?`check_task22j_*`

缂哄彛锛?
- 澶氫釜鏃╂湡鑴氭湰榛樿 8000/5432锛屼笉閫傞厤褰撳墠鏈満 8010/55432銆?- 閮ㄥ垎鑴氭湰浼氬啓娴嬭瘯鏁版嵁骞惰蒋娓呯悊锛岄渶鍖哄垎鐪熷疄楠屾敹涓庢紨绀烘暟鎹€?- 鐪熷疄澶栭儴 API銆丱CR銆丩oongArch/Kylin銆乪mbedding/pgvector 娌℃湁 passed 娴嬭瘯銆?- 缂哄皯鎬ц兘銆佸苟鍙戙€佸畨鍏ㄣ€丷AG 璐ㄩ噺璇勪及娴嬭瘯銆?- blocked/fallback 楠岃瘉涓嶈兘绛夊悓鐪熷疄鑳藉姏楠屾敹銆?
## 13. 鏂囨。涓庡浼犺〃杩伴闄?
蹇呴』閬垮厤鐨勮娉曪細

- 鈥滀簯绔湡瀹炴ā鍨嬪凡鍦ㄧ嚎閫氳繃鈥?- 鈥滄湰鍦?GGUF 宸茬湡瀹炴帹鐞嗏€?- 鈥渕imo-2.5 澶氭ā鎬?API 宸茬湡瀹炴帴閫氣€?- 鈥淥CR 宸茬湡瀹炶瘑鍒€氳繃鈥?- 鈥淟oongArch/Kylin 宸插疄鏈洪儴缃查€氳繃鈥?- 鈥減gvector / embedding / hybrid retrieval 宸插畬鎴愨€?- 鈥淣eo4j / 澶栭儴鍥炬暟鎹簱宸叉帴鍏モ€?- 鈥滃浘鍍忔晠闅滆嚜鍔ㄨ瘑鍒凡瀹屾垚鈥?- 鈥滅郴缁熷彲鏇夸唬涓撳鑷姩鍒ゆ柇鏁呴殰鈥?- 鈥滅郴缁熷彲鑷姩鍒涘缓/瀹屾垚缁翠慨浠诲姟鈥?- 鈥滅敓浜х骇閮ㄧ讲瀹屽叏瀹屾垚鈥?
鍙互瀹夊叏澹版槑锛?
- PostgreSQL 鏍稿績涓氬姟闂幆宸插湪鏈湴寮€鍙戠幆澧冮獙璇併€?- 鐭ヨ瘑搴撲笂浼犮€佽В鏋愩€佸垏鐗囥€佹绱㈠拰鏉ユ簮杩芥函宸插叿澶囧熀纭€鑳藉姏銆?- 璇婃柇銆丼OP銆佷换鍔°€佽褰曚腑蹇冦€佸獟浣撹祫鏂欍€佺煡璇嗗浘璋卞叿澶囧熀纭€宸ョ▼闂幆銆?- 澶氭櫤鑳戒綋鍏峰鑽夌銆佸鎵广€乤rtifact銆佹樉寮忚浆鎹㈡鏋躲€?- External API Provider Gateway 鍏峰 provider/route/log/status/dry-run/mock-run 鎺ュ叆浣嶅拰鑴辨晱鏃ュ織銆?- OCR銆丮IMO銆丆loud Vision銆佹湰鍦版ā鍨嬩负鍙€夊寮猴紝褰撳墠榛樿 blocked/disabled銆?
## 14. 鍚庣画淇璺嚎

### Task 24B锛歱gvector + embedding + hybrid RAG

- 鐩爣锛氳ˉ浼佷笟绾ц涔夋绱€?- 娑夊強鏂囦欢锛歮odels銆乻chemas銆乺epositories銆乺etrieval service銆丄lembic銆乻cripts銆乫rontend type銆?- 楠屾敹锛氱湡瀹?embedding 鍐欏叆銆乸gvector 鏌ヨ銆乲eyword+vector hybrid銆乺erank銆佽瘎浼伴泦鎸囨爣銆?
### Task 24C锛氱湡瀹?MIMO / OCR / CLOUD_LLM real-call

- 鐩爣锛氬皢 External API Provider Gateway 浠?dry-run 鎺ュ叆浣嶅崌绾т负鍙帶鐪熷疄澶栧懠銆?- 娑夊強鏂囦欢锛歟xternal API adapters銆乬ateway銆乺equest builder銆乺esponse parser銆乵ultimodal normalizer銆乻cripts銆?- 楠屾敹锛氭棤 Key 娉勯湶銆佺湡瀹炶皟鐢ㄥ彲閰嶇疆銆佽秴鏃?澶辫触/fallback 鍙祴銆佹棩蹇楄劚鏁忋€?
### Task 24D锛氬畨鍏ㄤ笌瀵嗛挜瀹¤

- 鐩爣锛氱敓浜у瘑閽ャ€丷BAC銆乺ate limit銆佽姹備綋澶у皬闄愬埗銆丆ORS銆佹棩蹇楄劚鏁忓姞鍥恒€?- 娑夊強鏂囦欢锛歝onfig銆乨ependencies銆乵iddleware銆乻cripts銆乨ocs銆?- 楠屾敹锛氱敓浜?placeholder 鎷掔粷鍚姩銆佽秺鏉冪煩闃甸€氳繃銆佹晱鎰熷瓧娈垫壂鎻忛€氳繃銆?
### Task 24E锛氳浆鎹㈣褰曡〃涓庡苟鍙戦槻閲嶅

- 鐩爣锛氫负 artifact conversion 澧炲姞鐙珛琛ㄣ€佸敮涓€绾︽潫銆佹挙閿€/浣滃簾鍜屽苟鍙戝畨鍏ㄣ€?- 娑夊強鏂囦欢锛歮odels銆乵igration銆乺epository銆乧onversion service銆乫rontend conversion UI銆乼ests銆?- 楠屾敹锛氬苟鍙戝弻璇锋眰浠呭垱寤轰竴娆★紱杞崲鍘嗗彶鍙煡锛涘け璐ュ彲杩借釜銆?
### Task 24F锛歀oongArch/Kylin 閮ㄧ讲楠屾敹

- 鐩爣锛氬湪鐪熷疄鐩爣鏈哄畬鎴?native PostgreSQL銆乿env銆乻ystemd銆丯ginx銆侀潤鎬佸墠绔拰涓氬姟闂幆銆?- 娑夊強鏂囦欢锛歞eploy scripts銆乨ocs銆乻ystemd/nginx templates銆乤cceptance scripts銆?- 楠屾敹锛氬疄鏈烘棩蹇椼€佹埅鍥俱€佸仴搴锋鏌ャ€佷笂浼犳绱㈤棴鐜€佹湇鍔￠噸鍚仮澶嶃€?
### Task 24G锛氭姤鍛婂鍑恒€侀€氱煡銆佽繍缁村寮?
- 鐩爣锛氳ˉ浼佷笟杩愮淮浣撻獙銆?- 娑夊強鏂囦欢锛歳ecord/report services銆乫rontend銆乻cripts銆?- 楠屾敹锛氬鍑烘姤鍛娿€佹搷浣滃璁°€佹棩蹇楀綊妗ｃ€佸浠芥仮澶嶃€佸憡璀﹂€氱煡銆?
## 15. No-package Confirmation

- delivery zip锛氭湰浠诲姟鏈敓鎴愩€?- delivery/锛氭湰浠诲姟鏈洿鏂般€?- delivery_staging锛氭湰浠诲姟鏈垱寤恒€?- Compress-Archive锛氭湰浠诲姟鏈墽琛屻€?
## 16. Git 鐘舵€?
- git add锛氭湭鎵ц銆?- git commit锛氭湭鎵ц銆?- git status summary锛氬綋鍓嶅伐浣滄爲涓嶆槸骞插噣鐘舵€侊紱瀛樺湪澶ч噺宸蹭慨鏀广€佸凡鍒犻櫎鍜屾湭璺熻釜鏂囦欢锛屽寘鍚?backend/frontend/docs/static frontend 鍙樺寲锛屼互鍙婃湭璺熻釜 `docs.zip`銆?

## Task 24D Update: Security Hardening Follow-up

Task 24D addresses the security gaps identified in this audit by adding production startup validation, controlled CORS settings, request-size middleware, lightweight rate limiting, secret scanning, log sanitization, upload/path traversal tests, RBAC matrix tests, and sanitized `/api/system/status` security fields.

Remaining audit boundary: real exposed keys must still be rotated by the user before production or real-call acceptance; LoongArch/Kylin real-machine deployment and real external provider calls remain outside Task 24D.

## Task 24E Update: Conversion Audit Gap Closed

The previous artifact conversion gap is addressed by Task 24E through `agent_artifact_conversions`, a database unique constraint, row-level conversion locking, conversion history APIs, failed-conversion recording, and browser-visible conversion history. Remaining boundaries still include no package generation, no external real-call acceptance, and no LoongArch/Kylin real-machine acceptance.

