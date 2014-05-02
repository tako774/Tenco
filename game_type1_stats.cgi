#!/usr/bin/ruby

# ゲーム統計ページCGI
begin
	# 開始時刻
	now = Time.now
	# リビジョン
	REVISION = 'R0.00'
	DEBUG = true

	$LOAD_PATH.unshift './common'
	$LOAD_PATH.unshift './entity'

	require 'db'
	require 'time'
	require 'logger'
	require 'utils'
	require 'json'
	require 'setting'
	require 'erubis'
	include Erubis::XmlHelper

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

	# 最大受付POSTデータサイズ（byte）
	MAX_POST_DATA_BYTES = 10000;
	# バリデーション用文字列
	ID_REGEX = /\A[0-9]+\z/

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
									
		game_id = nil # ゲームID
		
		LINK_INTERNAL_ERB_PATH = "./link_internal.erb" # 内部リンクERBパス
		LINK_ERB_PATH = "./link.erb" # リンクERBパス
		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		
		# クエリストリング分解・取得
		query = parse_query_str(ENV['QUERY_STRING'])
				
		# 入力バリデーション
		unless (
			query['game_id'] and
			query['game_id'] =~ ID_REGEX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "入力データが正しくありません\ninput data validation error.\n"
			raise "input data validation error."
		else
			game_id = query['game_id']
		end
		
		# キャッシュフォルダがなければ生成
		Dir.mkdir(CACHE_BASE, 0700) unless File.exist?(CACHE_BASE)
		Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
		Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

		# キャッシュパス設定・プロセスロックファイルパス設定
		cache_html_path = "#{CACHE_DIR}/#{File::basename(__FILE__)}_#{game_id}.html"
		cache_html_header_path  = "#{cache_html_path}.h"	
		cache_lock_path = "#{CACHE_LOCK_DIR}/#{File::basename(__FILE__)}_#{game_id}.lock"
		
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
						game = nil # ゲーム情報
						game_type1_range_stats = {} # ゲームアカウント情報、キー1：使用キャラ、キー2：レート区切り位置
						type1 = {} # キャラ区分値=>キャラ名のハッシュ
						range_step = 0.1 # レート分布情報の区切り割合
						rank_ranges_temp = []
						rank_ranges = {} # レート分布情報の区切りたち、キー：区切り位置の割合、値：画面上の表示名
						gtrr_same_rank_data = []  # レート区切り位置が同一のキャラ別レートデータ
						gtrr_same_rank_json = nil # レート区切り位置が同一のキャラ別レートデータ(json形式)
						
						# DB接続取得
						db = DB.getInstance							
						
						# ゲーム情報取得
						require 'Game'
						res = db.exec(<<-"SQL")
							SELECT
								*
							FROM
								games
							WHERE
								id = #{game_id.to_i}
						SQL
						
						if res.num_tuples != 1 then
							res.clear
							res_status = "Status: 400 Bad Request\n"
							res_body = "該当ゲーム情報は登録されていません\n"
							raise "該当ゲーム情報は登録されていません"
						else
							game = Game.new
							res.num_fields.times do |i|
								game.instance_variable_set("@#{res.fields[i]}", res[0][i])
							end
							res.clear	
						end

						# レート分布情報の区切り生成
						0.step(1, range_step) do |r|
							rank_ranges_temp << r
						end
						
						# レート分布情報の一時テーブル作成
						db.exec(<<-"SQL")
							CREATE LOCAL TEMP TABLE game_type1_rank_ranges (
							  rank_range real NOT NULL
							);
						SQL
						db.exec(<<-"SQL")
							INSERT INTO game_type1_rank_ranges (
							  rank_range
							)
							VALUES
							  #{(rank_ranges_temp.map { |r| "(#{r})" }).join(",\n")}
							;
						SQL
						
						# レート分布情報とりなおし
						res = db.exec(<<-"SQL")
							SELECT
							  *
							FROM
							  game_type1_rank_ranges
							;
						SQL
						
						res.each do |r|
							range = r[0].to_f
							if range == 0.0 then
								rank_ranges[range.to_f] = "Top"
							elsif range == 1.0 then
								rank_ranges[range.to_f] = "Last"
							else
								rank_ranges[range.to_f] = "#{(range.to_f * 100).to_i}%"
							end
						end
							
						# ゲームキャラ別レート区切り統計情報取得
						require 'GameType1RangeStat'
						res = db.exec(<<-"SQL")
							SELECT
							  br.*, gar.rating
							FROM
							  game_account_ratings gar,
							  (
								SELECT
								  gar2.game_id,
								  gar2.type1_id,
								  gtrr.rank_range,
								  CASE
								    WHEN trunc(MAX(gar2.game_each_type1_ratings_rank) * gtrr.rank_range) < 1 THEN 1
									ELSE trunc(MAX(gar2.game_each_type1_ratings_rank) * gtrr.rank_range)
								  END AS border_rank
								FROM
								  game_type1_rank_ranges gtrr
									LEFT OUTER JOIN
									  game_account_ratings gar2
									ON
									  TRUE
								WHERE
								  gar2.game_id = #{game_id.to_i}
								  AND gar2.type1_id != 99999998
								GROUP BY
								  gar2.game_id, gar2.type1_id, gtrr.rank_range
							  ) AS br
							WHERE
							  gar.game_id = br.game_id
							  AND gar.type1_id = br.type1_id 
							  AND gar.game_each_type1_ratings_rank = br.border_rank
						SQL
						
						res.each do |r|
							gtrs = GameType1RangeStat.new
							res.num_fields.times do |i|
								gtrs.instance_variable_set("@#{res.fields[i]}", r[i])
							end
							game_type1_range_stats[gtrs.type1_id.to_i] ||= {}
							game_type1_range_stats[gtrs.type1_id.to_i][gtrs.rank_range.to_f] = gtrs
						end
						res.clear
						
						# レート区切り位置が同一のキャラ別レートデータ作成
						
						game_type1_range_stats.each do |type1_id, r_rs|
							type1_id_rate = []
							r_rs.each do |r_r, gtrs|
								type1_id_rate << [type1_id.to_i, gtrs.rating.to_f.round]
							end
							gtrr_same_rank_data << type1_id_rate
						end
						
						gtrr_same_rank_json = gtrr_same_rank_data.to_json
							
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
						
					rescue => ex
						res_status = "Status: 500 Server Error\n"
						res_body << "サーバーエラーです。ごめんなさい。\n"
						raise ex
					ensure
						db.close if db
					end
					
					### キャッシュHTML出力
					
					# 内部リンク 部生成
					link_internal_html = Erubis::Eruby.new(File.read(LINK_INTERNAL_ERB_PATH)).result(binding)
					# link 部生成
					link_html = Erubis::Eruby.new(File.read(LINK_ERB_PATH)).result(binding)
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

