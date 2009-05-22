#!/usr/bin/ruby

# ゲームキャラ対キャラ統計ページCGI
begin
	# 開始時刻
	now = Time.now
	# リビジョン
	REVISION = 'R0.01'
	DEBUG = false

	$LOAD_PATH.unshift './common'
	$LOAD_PATH.unshift './entity'

	require 'db'
	require 'time'
	require 'logger'
	require 'utils'
	include Utils
	require 'erb'
	include ERB::Util

	# TOP ページ URL
	TOP_URL = 'http://tenco.xrea.jp/'
	# TOP ディレクトリパス
	TOP_DIR = '.'
	# ログファイルパス
	LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"
	# キャッシュフォルダパス
	CACHE_DIR = "#{TOP_DIR}/cache/#{File::basename(__FILE__)}"
	# キャッシュロックフォルダパス
	CACHE_LOCK_DIR = "#{TOP_DIR}/cache/lock/#{File::basename(__FILE__)}"
	# キャッシュをつかったかどうか
	is_cache_used = false
	# 最大受付POSTデータサイズ（byte）
	MAX_POST_DATA_BYTES = 10000;

	# HTTP/HTTPSレスポンス文字列
	res_status = "Status: 500 Server Error\n"
	res_header = "content-type:text/plain; charset=utf-8\n"
	res_body = ""

	# ログ開始
	logger = Logger.new(LOG_PATH)
	logger.level = Logger::DEBUG
rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
end

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		query = {} # クエリストリング
		db = nil   # DB接続 
									
		game_id = nil # ゲームID

		game = nil # ゲーム情報
		game_type1_vs_type1_stats = {} # ゲームアカウント情報、キー1：使用キャラ、キー2：対戦相手キャラ
		type1 = {} # キャラ区分値=>キャラ名のハッシュ
		cache_expires = nil # 生成するキャッシュの期限
		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		LINK_ERB_PATH = "./link.erb" # リンクERBパス
		
		# クエリストリング分解・取得
		query = parse_query_str(ENV['QUERY_STRING'])
				
		# 入力バリデーション
		unless (
			query['game_id'] and
			query['game_id'] != ''
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "入力データが正しくありません\ninput data validation error.\n"
			raise "input data validation error."
		else
			game_id = query['game_id']
		end
		
		# キャッシュフォルダがなければ生成
		Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
		Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

		# キャッシュパス設定・プロセスロックファイルパス設定
		cache_html_path = "#{CACHE_DIR}/#{File::basename(__FILE__)}.html"
		cache_html_header_path  = "#{cache_html_path}.h"	
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
					
						# キャッシュの有効期限
						cache_expires = (now + 60 * 60) - now.min * 60 - now.sec
					
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
						
						# ゲームキャラ対キャラ統計情報取得
						require 'GameType1VsType1Stat'
						res = db.exec(<<-"SQL")
							SELECT
								*
							FROM
								game_type1_vs_type1_stats
							WHERE
								date_time = ( SELECT MAX(date_time) FROM game_type1_vs_type1_stats )
								AND game_id = #{game_id.to_i}
						SQL
						
						res.each do |r|
							gtbts = GameType1VsType1Stat.new
							res.num_fields.times do |i|
								gtbts.instance_variable_set("@#{res.fields[i]}", r[i])
							end
							game_type1_vs_type1_stats[gtbts.type1_id.to_i] ||= {}
							game_type1_vs_type1_stats[gtbts.type1_id.to_i][gtbts.matched_type1_id.to_i] = gtbts
						end
						res.clear
					
						# Type1 区分値取得
						res = db.exec(<<-"SQL")
							SELECT
								segment_values.segment_value AS value, segment_values.name AS name
							FROM
								segment_values, games
							WHERE
								games.id = #{game_id.to_i}
							AND segment_values.segment_id = games.type1_segment_id
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
					require 'erb'
					include ERB::Util
					
					# link 部生成
					link_html = ERB.new(File.read(LINK_ERB_PATH), nil, '-').result(binding)
					# footer 部生成
					footer_html = ERB.new(File.read(FOOTER_ERB_PATH), nil, '-').result(binding)
					
					File.open(cache_html_path, 'w') do |w|
						w.flock(File::LOCK_EX)
						w.puts ERB.new(File.read("#{File::basename(__FILE__, '.*')}.erb"), nil, '-').result(binding)
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
