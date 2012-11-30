#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now
	# リビジョン
	REVISION = 'R0.68'
	DEBUG = false

	$LOAD_PATH.unshift './common'
	$LOAD_PATH.unshift './entity'
	$LOAD_PATH.unshift './dao'

	require 'time'
	require 'logger'
	require 'segment_const'
	require 'utils'
	require 'setting'

	# 設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']
	# TOP ディレクトリパス
	TOP_DIR = '.'
	# ログファイルパス
	LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "#{TOP_DIR}/log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"
	
	# キャッシュの有効期限
	cache_expires = (now + 60 * 60) - now.min * 60 - now.sec
	# キャッシュ親パス
	CACHE_BASE="./cache/#{cache_expires.strftime('%Y%m%d%H%M%S')}"
	# キャッシュフォルダパス
	CACHE_DIR = "#{CACHE_BASE}/#{File::basename(__FILE__)}"
	# キャッシュロックフォルダパス
	CACHE_LOCK_DIR = "#{CACHE_BASE}/lock_#{File::basename(__FILE__)}"
	# キャッシュをつかったかどうか
	is_cache_used = false
	
	# 件数制限
	MAX_TRACK_RECORDS = 100
	# 推定レート表示対象レート
	ESTIMATION_LIMIT_RATE = Float::MAX

	# HTTP/HTTPSレスポンス文字列
	res_status = "Status: 500 Server Error\n"
	res_header = "content-type:text/plain; charset=utf-8\n"
	res_body = ""

	# ログ開始
	logger = Logger.new(LOG_PATH)
	logger.level = Logger::DEBUG

	# アクセスログ記録
	access_logger = Logger.new(ACCESS_LOG_PATH)
	access_logger.level = Logger::DEBUG
	access_logger.info(
		[
			"",
			now.strftime('%Y/%m/%d %H:%M:%S'),
			ENV['REMOTE_ADDR'],
			ENV['HTTP_USER_AGENT'],
			ENV['REQUEST_URI'],
			File::basename(__FILE__)
		].join("\t")
	)
	
rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
	exit
end

		
if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		query = {} # クエリストリング
		db = nil   # DB接続 
		
		track_record_ids = [] # 対戦結果ID一覧
		track_records = []    # 対戦結果
		type1 = {}            # プレイヤー属性１区分値
		type1_h = {}          # プレイヤー属性１区分値（HTML エスケープ済み）
		ratings = []          # プレイヤーのレーティング 
		estimate_ratings = {} # プレイヤーのレート推定値
		account_tags = []     # アカウントタグ情報
		player2_account_ids = []   # 対戦相手アカウントID一覧
		matched_game_accounts = [] # 対戦相手情報
		account = nil    # 対象アカウントの情報
		other_games = [] # 対象アカウントのマッチ済み他ゲームID
		affiliates_data = nil # アフィリエイトデータ　カテゴリ => { 店舗名 => { meta => メタデータハッシュ, item => { item_id => アイテムデータハッシュ } } }
		account_twitter_data = {} # twitter データ account_id => [{ :uri => uri, :screen_name => screen_name, :profile_image_url => profile_image_url }]
		
		META_INFO_ERB_PATH = "./game_account_meta_info.erb" # ヘッダメッセージERBパス
		LINK_ERB_PATH   = "./link.erb"   # リンクERBパス
		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		AFFILIATE_ERB_PATH = "./affiliate.erb" # アフィリエイトERBパス
		AFFILIATE_YAML_PATH = "./affiliate.yaml" # アフィリエイトYAMLパス
		
		# クエリストリング分解
		query = parse_query_str(ENV['QUERY_STRING'])
		
		if (query['game_id'] and query['game_id'] !='' and query['account_name'] and query['account_name'] != '') then
			account_name = query['account_name']  # アカウント名
			game_id = query['game_id'].to_i       # ゲーム番号
			output = query['output'] || 'html'    # 出力形式
			
			
			# キャッシュフォルダがなければ生成
			Dir.mkdir(CACHE_BASE, 0700) unless File.exist?(CACHE_BASE)
			Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
			Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

			# キャッシュパス設定・プロセスロックファイルパス設定
			cache_xml_path  = "#{CACHE_DIR}/#{game_id.to_s}-#{account_name}.xml"
			cache_xml_header_path  = "#{cache_xml_path}.h"
			cache_html_path = "#{CACHE_DIR}/#{game_id.to_s}-#{account_name}.html"
			cache_html_header_path = "#{cache_html_path}.h"
			cache_lock_path = "#{CACHE_LOCK_DIR}/#{game_id.to_s}-#{account_name}.lock"
			
			# キャッシュパスのバリデーション
			if cache_xml_path =~ /\.{2}/ or cache_html_path =~ /\.{2}/ or cache_lock_path =~ /\.{2}/ then
				raise "ディレクトリトラバーサルの疑いがあります"
			end
			
			# デバッグ時か、キャッシュが無いかあってもサイズ0か、
			# ロックファイルが無いか、（＝キャッシュの再生成を行う条件）、キャッシュ生成
			unless (!DEBUG and
				File.exist?(cache_html_path) and (File.size(cache_html_path) != 0) and
				File.exist?(cache_html_header_path) and (File.size(cache_html_header_path) != 0) and
				File.exist?(cache_xml_path) and (File.size(cache_xml_path) != 0) and
				File.exist?(cache_xml_header_path) and (File.size(cache_xml_header_path) != 0) and
				File.exist?(cache_lock_path)
			) then			
				### キャッシュ生成
				# 生成プロセスをひとつだけにするために、プロセスロックする
				File.open(cache_lock_path, 'w') do |f|
					if f.flock(File::LOCK_EX | File::LOCK_NB) then	
						begin
							require 'db'
							require 'utils'
							require 'time'
							require 'erubis'
							include Erubis::XmlHelper
							require 'html_helper'
							
							# DB接続
							db = DB.getInstance
							
							# アカウント情報取得
							require 'AccountDao'
							require 'Account'
							account = AccountDao.new.get_account_by_name(account_name)
							
							# ゲーム情報を取得
							require 'GameDao'
							require 'Game'
							game = GameDao.new.get_game_by_id(game_id)
							
							# 該当アカウントのゲームごとの情報を取得
							require 'GameAccount'
							res = db.exec(<<-"SQL")
								SELECT
									ga.*,
									gc.name AS cluster_name
								FROM
									game_accounts ga
										LEFT OUTER JOIN 
											game_clusters gc
										ON
											gc.game_id = ga.game_id
											AND gc.cluster_id = ga.cluster_id
								WHERE
									ga.game_id = #{game_id.to_i}
									AND ga.account_id = #{account.id.to_i}
								SQL
							
							if res.num_tuples != 1 then
								game_account = GameAccount.new
								game_account.game_id = game_id.to_i
								game_account.account_id = game_id.to_i
								game_account.rep_name = account_name.to_s
								res.clear
								# res_status = "Status: 200 OK\n"
								# res_body = "このゲームでの対戦情報が未報告か、サーバーが未処理です。\n"
								# res_body << "すでに報告している場合には、申し訳ありませんが、少々お待ちください。\n"
								# raise "ゲーム・アカウント情報が未登録です"
							else
								game_account = GameAccount.new
								res.num_fields.times do |i|
									game_account.instance_variable_set("@#{res.fields[i]}", res[0][i])
								end
								res.clear
							end
							
							# NGワード伏字化
							game_account.rep_name = hide_ng_words(game_account.rep_name)
							
							# 該当アカウントの他のマッチ済み全ゲーム情報を取得
							require 'Game'
							res = db.exec(<<-"SQL")
								SELECT
									g.*
								FROM
									games g,
									game_accounts ga
								WHERE
									g.id = ga.game_id
									AND	g.id != #{game_id.to_i}
									AND ga.account_id = #{account.id.to_i}
								ORDER BY
									g.id
							SQL
							
							res.each do |r|
								g = Game.new
								res.num_fields.times do |i|
									g.instance_variable_set("@#{res.fields[i]}", r[i])
								end
								other_games << g
							end
							
							# アカウントのレーティング情報を取得
							require 'GameAccountRating'
							res = db.exec(<<-"SQL")
								SELECT
								  r.*
								FROM
								  game_account_ratings r
								WHERE
								  r.game_id = #{game_id.to_i}
								  AND r.account_id = #{account.id.to_i}
								ORDER BY
								  r.ratings_deviation,
								  r.rating DESC
								SQL
							
							res.each do |r|
								rating = GameAccountRating.new
								res.num_fields.times do |i|
									rating.instance_variable_set("@#{res.fields[i]}", r[i])
								end
								ratings << rating
							end
							res.clear
							
							# アカウントタグ情報取得
							require 'AccountTag'
							res = db.exec(<<-"SQL")
								SELECT
									at.tag_id,
									COALESCE(at.tag_disp_name, t.name) AS tag_disp_name
								FROM
									account_tags at,
									tags t
								WHERE
									at.account_id = #{account.id.to_i}
									AND at.tag_id = t.id 
							SQL
							
							res.each do |r|
								account_tag = AccountTag.new
								res.num_fields.times do |i|
									account_tag.instance_variable_set("@#{res.fields[i]}", r[i])
								end
								account_tags << account_tag
							end
							res.clear
							
							# アカウント公開プロフィール情報取得
							require 'AccountProfileDao'
							require 'AccountProfile'
							account_profiles = {}
							
							AccountProfileDao.new.get_by_account_name(account_name, { :visibility_check => true } ).each do |ap|
								account_profiles[ap.class_id.to_i] ||= {:class_display_name => ap.class_display_name}
								account_profiles[ap.class_id.to_i][:profiles] ||= []
								account_profiles[ap.class_id.to_i][:profiles] << ap
							end
							
							# アカウントの対戦記録を取得
							# 未マッチの場合、player2 の名前は暗号化させるため、パスワードを渡す
							require 'TrackRecordDao'
							require 'TrackRecord'
							
							# 対戦結果ID一覧取得
							trd = TrackRecordDao.new
							track_record_ids = trd.get_ids_by_game_account(game_id, account.id)
							
							# 対戦結果取得
							if track_record_ids.length > 0 then
								track_records = trd.get_track_records_by_ids(track_record_ids[0..MAX_TRACK_RECORDS - 1], account.data_password)
								track_records.sort! { |a,b| b.play_timestamp <=> a.play_timestamp }
							end

							# 推定レートの値を取得
							# アカウントのレートが一定以上の場合のみ取得
							require 'GameProfileUtil'
							
							# 対象のゲーム内プロファイル名を取得
							game_profile_name_counts = {}
							est_target_names = []
							track_records.each do |t|
								if (
									t.player2_account_name and
									t.player2_account_del_flag.to_i == 0
								) then
									game_profile_name_counts[t.player1_name] ||= 0
									game_profile_name_counts[t.player1_name] += 1
								end
							end
							
							game_profile_name_counts.to_a.each do |name, count|
								if count >= 10 then
									est_target_names << name
								end
							end
							
							est_target_names << game_account.rep_name unless est_target_names.index(game_account.rep_name)
							
							# 対象の type1_id を取得
							est_type1_ids = []
							ratings.each do |r|
								if (
								  r.ratings_deviation.to_f < 150 &&
								  r.matched_accounts.to_i >= 5 &&
								  r.rating.to_f.round >= ESTIMATION_LIMIT_RATE
								) then
									est_type1_ids << r.type1_id.to_i
								end
							end
							
							# 推定レート取得
							if est_type1_ids.length > 0 then
								estimate_ratings = GameProfileUtil.estimate_rating(est_target_names, game_id.to_i, est_type1_ids)
							end

							
							# ゲーム内プロファイル名NGワード伏字化
							track_records.each do |t|
								t.player1_name = hide_ng_words(t.player1_name)
								t.player2_name = hide_ng_words(t.player2_name)
							end
							
							# 対戦相手一覧取得
							require 'GameAccountDao'
							gad = GameAccountDao.new
							
							# 対戦相手のアカウントID一覧取得
							player2_account_ids = gad.get_matched_account_ids(game_id, account.id)
							
							# 対戦相手一覧の情報取得
							matched_game_accounts = gad.get_game_accounts(game_id, player2_account_ids)
							
							# twitter データ取得
							require 'ExServiceAccountDao'
							esa_dao = ExServiceAccountDao.new
							account_twitter_data = esa_dao.get_twitter_data_by_account_ids([account.id] + player2_account_ids)
							
							# Type1 区分値取得
							res = db.exec(<<-"SQL")
								SELECT
									type1_id, name
								FROM
									game_type1s
								WHERE
									game_id = #{game_id.to_i}
							SQL
							
							res.each do |r|
								type1[r[0].to_i] = r[1]
							end
							res.clear
							
							# 仮想 Type1 区分値取得
							SEG_V[:virtual_type1].each_value do |seg|
								type1[seg[:value].to_i] = seg[:name]
							end

							# 区分値を HTML エスケープしておく（h メソッドの呼び出し削減）
							type1.each do |k, v|
								type1_h[k] = h v
							end
							
						rescue => ex
							res_status = "Status: 500 Server Error\n"
							res_body << "サーバーエラーです。ごめんなさい。\n" unless res_body
							raise ex
						ensure
							db.close if db
						end
						
						### キャッシュXML生成
						require 'rexml/document'
						
						# XML生成
						xml = REXML::Document.new
						xml << REXML::XMLDecl.new('1.0', 'UTF-8')
						
						# gameAccount 要素生成
						root = xml.add_element('gameAccount')
						
						# account 要素生成
						account_element = root.add_element('account')
						account_element.add_element('name').add_text(account_name)
						
						# account/game 要素生成
						game_element = account_element.add_element('game')
						game_element.add_element('id').add_text(game_id.to_s)
						game_element.add_element('name').add_text(game.name)
						game_element.add_element('representative_account_name').add_text(game_account.rep_name)
						
						# account/game/cluster 要素生成
						account_cluster_element = game_element.add_element('account_cluster')
						account_cluster_element.add_element('name').add_text(game_account.cluster_name.to_s)
						
						# account/game/type1 要素生成
						if account.show_ratings_flag.to_i != 0 then
							# type1 要素生成
							ratings.each do |r|
								# ランダムを省く暫定対応
								unless r.type1_id.to_i == SEG_V[:virtual_type1][:random][:value].to_i
									type1_element = game_element.add_element('type1')
									type1_element.add_element('id').add_text(r.type1_id)
									type1_element.add_element('name').add_text(type1[r.type1_id.to_i])
									type1_element.add_element('rating').add_text("#{r.rating.to_f.round.to_s}±#{r.ratings_deviation.to_f.floor.to_s}")
									type1_element.add_element('rating_value').add_text(r.rating.to_f.round.to_s)
									type1_element.add_element('ratings_deviation').add_text(r.ratings_deviation.to_f.floor.to_s)
									type1_element.add_element('matched_accounts').add_text(r.matched_accounts)
									type1_element.add_element('match_counts').add_text(r.match_counts)
								end
							end	
						end
						
						# account/profile 要素生成
						account_profiles.keys.sort.each do |class_id|
							aps = account_profiles[class_id]
							aps[:profiles].each do |ap|
								profile_element = account_element.add_element('profile')
								profile_element.add_element('property', {'title' => ap.display_name, 'class' => ap.class_name, 'class_title' => ap.class_display_name}).add_text ap.name
								profile_element.add_element('value').add_text ap.value
								profile_element.add_element('uri').add_text ap.uri if ap.uri
							end
						end
						
						# キャッシュXML/ヘッダ出力
						File.open(cache_xml_path, 'w') do |w|
							w.flock(File::LOCK_EX)
							w.puts xml.to_s
							File.open(cache_xml_header_path, 'w') do |wh|
								wh.flock(File::LOCK_EX)
								wh.puts "Content-Type:text/xml; charset=utf-8"
								wh.puts "Access-Control-Allow-Origin: *"
								wh.puts "Last-Modified: #{now.httpdate}"
								wh.puts "Expires: #{cache_expires.httpdate}"
							end
						end
						
						### キャッシュHTML出力
						
						# ヘッダメッセージ 部生成
						meta_info_html = Erubis::Eruby.new(File.read(META_INFO_ERB_PATH)).result(binding)
						# リンク 部生成
						link_html = Erubis::Eruby.new(File.read(LINK_ERB_PATH)).result(binding)
						# footer 部生成
						footer_html = Erubis::Eruby.new(File.read(FOOTER_ERB_PATH)).result(binding)
						
						# アフィリエイト 部生成
						affiliates_data = YAML.load_file(AFFILIATE_YAML_PATH)
						affiliate_html = Erubis::Eruby.new(File.read(AFFILIATE_ERB_PATH)).result(binding)
						
						# キャッシュHTML/ヘッダ出力
						File.open(cache_html_path, 'w') do |w|
							w.flock(File::LOCK_EX)
							w.puts Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}.erb")).result(binding)
							File.open(cache_html_header_path, 'w') do |wh|
								wh.flock(File::LOCK_EX)
								wh.puts "Content-Type:text/html; charset=utf-8"
								wh.puts "Last-Modified: #{now.httpdate}"
								wh.puts "Expires: #{cache_expires.httpdate}"
							end
						end

					else
						logger.info("Info: #{cache_lock_path} is locked. Wait unlocked.\n")
						# 先行プロセスがキャッシュを書き出すのを待つ
						f.flock(File::LOCK_EX)
						f.flock(File::LOCK_UN)
						is_cache_used = true
					end	# if f.flock(File::LOCK_EX | File::LOCK_NB) then	
				end # File.open(cache_lock_path, 'w') do |f|
			else
				is_cache_used = true
			end # unless (File.exist?(cache_html_path) and File.exist?(cache_xml_path)) then
			
			### 結果をセット
			if output == 'xml' then
				res_status = ""
				File.open(cache_xml_path, 'r') do |f|
					f.flock(File::LOCK_SH)
					res_body = f.read()
					File.open(cache_xml_header_path, 'r') do |fh|
						fh.flock(File::LOCK_SH)
						res_header = fh.read()
					end
				end
			else
				res_status = ""
				File.open(cache_html_path, 'r') do |f|
					f.flock(File::LOCK_SH)
					res_body = f.read()
					File.open(cache_html_header_path, 'r') do |fh|
						fh.flock(File::LOCK_SH)
						res_header = fh.read()
					end
				end
			end
			
			# 304 Not Modified 判定
			if ENV['HTTP_IF_MODIFIED_SINCE'] then
				if res_header =~ /Last-Modified:\s*([^\n]+)/i then
					last_modified = Time.httpdate($1)
					# 古いブラウザによる RFC2616 違反の HTTP ヘッダに対応
					since = Time.httpdate(ENV['HTTP_IF_MODIFIED_SINCE'].sub(/;.*\z/, ""))
					if last_modified <= since then
						res_status = "Status: 304 Not Modified\n"
						res_body = ""
					end
				end
			end
			
		else
			res_status = "Status: 400 Bad Request\n"
			res_body = "400 Bad Request\n"
		end	
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body = "サーバーエラーです。ごめんなさい。\n" unless res_body
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{now.to_s} #{File::basename(__FILE__)} #{REVISION}" 
			err_log.puts ENV['QUERY_STRING']
			err_log.puts ENV['HTTP_IF_MODIFIED_SINCE']
			err_log.puts ex.class.to_s
			err_log.puts ex.to_s
			err_log.puts ex.backtrace.join("\n").to_s
			err_log.puts
		end
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

begin
# HTTP レスポンス送信
print res_status
print res_header
print "\n"
print res_body

# ログ記録
	times = Process.times
	logger.debug(
		[
			File::basename(__FILE__),
			REVISION,
			Time.now - now,
			times.utime + times.stime,
			times.utime,
			times.stime,
			times.cutime,
			times.cstime,
			is_cache_used.to_s,
			ENV['QUERY_STRING']
		].join("\t")
	)
rescue
end

