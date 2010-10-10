#!/usr/bin/ruby

# インデックスページ作成CGI
begin
	# 開始時刻
	now = Time.now
	# リビジョン
	REVISION = 'R0.13'
	DEBUG = false

	# TOP ディレクトリパス
	TOP_DIR = '.'
	
	$LOAD_PATH.unshift "#{TOP_DIR}/common"
	$LOAD_PATH.unshift "#{TOP_DIR}/entity"
	$LOAD_PATH.unshift "#{TOP_DIR}/dao"

	require 'time'
	require 'logger'
	require 'utils'
	require 'setting'
	
	require 'Game'
	require 'GameDao'

	# 設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']
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
		
		games = {} # ゲーム情報
		game_stats = {} # ゲーム統計情報
		game_type1_stats = {} # キャラ別統計情報
		game_type1s = {} # キャラ名区分値
		
		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		
		# クエリストリング分解・取得
		query = parse_query_str(ENV['QUERY_STRING'])
		
		output = query['output'] || 'html'    # 出力形式
		
		# キャッシュフォルダがなければ生成
		Dir.mkdir(CACHE_BASE, 0700) unless File.exist?(CACHE_BASE)
		Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
		Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

		# キャッシュパス設定・プロセスロックファイルパス設定
		cache_html_path = "#{CACHE_DIR}/#{File::basename(__FILE__)}.html"
		cache_html_header_path = "#{cache_html_path}.h"	
		cache_lock_path = "#{CACHE_LOCK_DIR}/#{File::basename(__FILE__)}.lock"
		
		# キャッシュパスのバリデーション
		if cache_html_path =~ /\.{2}/ or cache_lock_path =~ /\.{2}/ then
			raise "ディレクトリトラバーサルの疑いがあります"
		end
		
		# デバッグ時か、キャッシュが無いかあってもファイルサイズが０か、
		# ロックファイルが無ければ（＝キャッシュの再生成を行う条件）、キャッシュ生成
		unless (
			!DEBUG and
			File.exist?(cache_html_path) and File.size(cache_html_path) != 0 and
			File.exist?(cache_html_header_path) and File.size(cache_html_header_path) != 0 and
			File.exist?(cache_lock_path)
		) then
					
			### キャッシュ生成
			# 生成プロセスをひとつだけにするために、プロセスロックする
			File.open(cache_lock_path, 'w') do |f|
				if f.flock(File::LOCK_EX | File::LOCK_NB) then	
					begin
						require 'db'
						require 'utils'
						include Utils
						require 'erubis'
						include Erubis::XmlHelper
													
						# DB接続
						db = DB.getInstance

						# 全ゲーム情報取得
						game_dao = GameDao.new
						games = game_dao.get_games
						
						# ゲーム統計情報を取得
						require 'GameStat'
						res = db.exec(<<-"SQL")
							SELECT
								g.id AS game_id,
								COALESCE(gs.date_time, CURRENT_TIMESTAMP) AS date_time,
								COALESCE(gs.accounts_count, 0) AS accounts_count,
								COALESCE(gs.matched_accounts_count, 0) AS matched_accounts_count,
								COALESCE(gs.accounts_type1s_count, 0) AS accounts_type1s_count,
								COALESCE(gs.matched_accounts_type1s_count, 0) AS matched_accounts_type1s_count,
								COALESCE(gs.track_records_count, 0) AS track_records_count,
								COALESCE(gs.matched_track_records_count, 0) AS matched_track_records_count
							FROM
								games g
								LEFT OUTER JOIN
									game_stats gs
								ON
									g.id = gs.game_id
						SQL
						
						res.each do |r|
							gs = GameStat.new
							res.fields.length.times do |i|
								gs.instance_variable_set("@#{res.fields[i]}", r[i])
							end
							game_stats[gs.game_id.to_i] = gs
						end
						res.clear
						
						# キャラ別統計情報を取得
						require 'GameType1Stat'
						res = db.exec(<<-"SQL")
							SELECT
								gt2.game_id AS game_id,
								gt2.type1_id AS type1_id,
								COALESCE(gts.date_time, CURRENT_TIMESTAMP) AS date_time,
								COALESCE(gts.accounts_count, 0) AS accounts_count,
								COALESCE(gts.track_records_count, 0) AS track_records_count,
								COALESCE(gts.wins, 0) AS wins,
								COALESCE(gts.loses, 0) AS loses
							FROM
								(
									SELECT
										g.id AS game_id,
										gt.type1_id AS type1_id
									FROM
										games g,
										game_type1s gt
									WHERE
										g.id = gt.game_id
								) AS gt2
								LEFT OUTER JOIN
									game_type1_stats gts
								ON
									    gt2.game_id = gts.game_id
									AND gt2.type1_id = gts.type1_id
							ORDER BY
								gt2.game_id,
								gt2.type1_id
							SQL
							
						res.each do |r|
							gts = GameType1Stat.new
							res.fields.length.times do |i|
								gts.instance_variable_set("@#{res.fields[i]}", r[i])
							end
							game_type1_stats[gts.game_id.to_i] ||= []
							game_type1_stats[gts.game_id.to_i] << gts
						end
						res.clear
						
						# Type1 区分値取得
						res = db.exec(<<-"SQL")
							SELECT
								game_id, type1_id, name
							FROM
								game_type1s
							WHERE
								game_id IN (#{games.keys.join(", ")})
						SQL
						
						res.each do |r|
							game_type1s[r[0].to_i] ||= {}
							game_type1s[r[0].to_i][r[1].to_i] = r[2]
						end
						res.clear
						
					rescue => ex
						res_status = "Status: 500 Server Error\n"
						res_body << "サーバーエラーです。ごめんなさい。\n"
						raise ex
					ensure
						db.close if db
					end
					
					### キャッシュHTML出力
					
					# game_stats 部生成
					index_game_stats_html = Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}_game_stats.erb")).result(binding)
					# footer 部生成
					footer_html = Erubis::Eruby.new(File.read(FOOTER_ERB_PATH)).result(binding)
					
					File.open(cache_html_path, 'w') do |w|
						w.flock(File::LOCK_EX)
						w.puts Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}.erb")).result(binding)
						# ヘッダ出力
						File.open(cache_html_header_path, 'w') do |wh|
							wh.flock(File::LOCK_EX)
							wh.puts "Content-Type:text/html; charset=utf-8"
							wh.puts "Last-Modified: #{now.httpdate}"
							wh.puts "Expires: #{cache_expires.httpdate}"
						end
					end
					
				else
					logger.info("Info: #{cache_lock_path} is locked.\n")
					# 先行プロセスがキャッシュを書き出すのを待つ
					f.flock(File::LOCK_EX)
					f.flock(File::LOCK_UN)
					is_cache_used = true
				end	# if f.flock(File::LOCK_EX | File::LOCK_NB) then	
			end # File.open(cache_lock_path, 'w') do |f|
		else
			is_cache_used = true
		end # unless (File.exist?(cache_html_path) then
		
		### 結果をセット
		res_status = ""
		File.open(cache_html_path, 'r') do |f|
			f.flock(File::LOCK_SH)
			res_body = f.read()
			File.open(cache_html_header_path, 'r') do |fh|
				fh.flock(File::LOCK_SH)
				res_header = fh.read()
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
				end
			end
		end
		
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body = "サーバーエラーです。ごめんなさい。\n" unless res_body
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{now.to_s} #{File::basename(__FILE__)} #{REVISION}" 
			err_log.puts ENV['QUERY_STRING']
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
			ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99]
		].join("\t")
	)
rescue
end

