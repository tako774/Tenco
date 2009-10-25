#!/usr/bin/ruby

### タグページ出力

# 開始時刻
begin
	now = Time.now
	# リビジョン
	REVISION = 'R0.03'
	DEBUG = false

	$LOAD_PATH.unshift './common'
	$LOAD_PATH.unshift './entity'

	require 'time'
	require 'logger'
	require 'segment_const'
	require 'utils'
	require 'setting'
	require 'erubis'
	include Erubis::XmlHelper

	# 設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']
	# ログファイルパス
	LOG_PATH = "./log/log_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "./log/error_#{now.strftime('%Y%m%d')}.log"
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

rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
end

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		query = {} # クエリストリング
		db = nil   # DB接続 

		LINK_ERB_PATH   = "./link.erb"   # リンクERBパス
		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		
		tag_name = nil # タグ名
		
		tag = {} # タグ情報
		games = {} # ゲーム情報、キー：ゲームID、値：ゲーム情報
		accounts = {} # タグ付けされているアカウントの情報 キー：アカウントID、値：アカウント情報
		game_accounts = {} # タグ付けされているゲームアカウント情報　キー：ゲームID、値：ゲームアカウント情報
		type1 = {} # Type1区分値、キー1：ゲームID、キー2：Type1ID、値：名前
				
		# クエリストリング分解
		query = parse_query_str(ENV['QUERY_STRING'])
		
		# バリデーション
		unless (
			query['tag_name'] and
			query['tag_name'] != ''
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "400 Bad Request\n"
		end	
		
		tag_name = query['tag_name']  # タグ名
		
		# キャッシュフォルダがなければ生成
		Dir.mkdir(CACHE_BASE, 0700) unless File.exist?(CACHE_BASE)
		Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
		Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

		# キャッシュパス設定・プロセスロックファイルパス設定
		cache_html_path = "#{CACHE_DIR}/#{u tag_name}.html"
		cache_html_header_path = "#{cache_html_path}.h"
		cache_lock_path = "#{CACHE_LOCK_DIR}/#{u tag_name}.lock"
		
		# キャッシュパスのバリデーション
		if cache_html_path =~ /\.{2}/ or cache_lock_path =~ /\.{2}/ then
			raise "ディレクトリトラバーサルの疑いがあります"
		end
		
		# デバッグ時か、キャッシュが無いかあってもサイズ0か、
		# ロックファイルが無いか、（＝キャッシュの再生成を行う条件）、キャッシュ生成
		unless (!DEBUG and
			File.exist?(cache_html_path) and (File.size(cache_html_path) != 0) and
			File.exist?(cache_html_header_path) and (File.size(cache_html_header_path) != 0) and
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
						
						# DB接続
						db = DB.getInstance
						
						# タグ情報取得
						require 'Tag'
						res = db.exec(<<-"SQL")
							SELECT
								id, name, "desc"
							FROM
								tags
							WHERE
								name = #{s(str_norm(tag_name))}
						SQL
						
						if res.num_tuples != 1 then
							res.clear
							res_status = "Status: 400 Bad Request\n"
							res_body = "該当タグは登録されていません\n"
							raise "該当タグは登録されていません(#{tag_name})"
						else
							tag = Tag.new
							res.num_fields.times do |i|
								tag.instance_variable_set("@#{res.fields[i]}", res[0][i])
							end
							res.clear	
						end
						
						# アカウント情報取得
						require 'Account'
						res = db.exec(<<-"SQL")
							SELECT
								a.id, a.name, a.show_ratings_flag
							FROM
								accounts a,
								account_tags at,
								tags t
							WHERE
								t.id = #{tag.id.to_i}
								AND at.tag_id = t.id
								AND at.account_id = a.id
								AND a.del_flag = 0
						SQL
						
						if res.num_tuples == 0 then
							res.clear
							res_status = "Status: 400 Bad Request\n"
							res_body = "該当タグが登録されたアカウントはいません\n"
							raise "該当タグが登録されたアカウントはいません(#{tag_name})"
						else
							res.each do |r|
								account = Account.new
								res.num_fields.times do |i|
									account.instance_variable_set("@#{res.fields[i]}", r[i])
								end
								accounts[account.id.to_i] = account
							end
							res.clear	
						end
						
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
								ga.account_id IN (#{accounts.keys.join(",")})
							SQL
						
						res.each do |r|
							ga = GameAccount.new
							res.num_fields.times do |i|
								ga.instance_variable_set("@#{res.fields[i]}", r[i])
							end
							# NGワード伏字化
							ga.rep_name = hide_ng_words(ga.rep_name)
							ga.cluster_name ||= "（新参加）"
							game_accounts[ga.game_id.to_i] ||= {}
							game_accounts[ga.game_id.to_i][ga.account_id.to_i] ||= ga
						end
						res.clear	
						
						# ゲーム情報を取得
						require 'Game'
						res = db.exec(<<-"SQL")
							SELECT
								*
							FROM
								games
							WHERE
								id IN (#{game_accounts.keys.join(",")})
						SQL
						
						res.each do |r|
							g = Game.new
							res.num_fields.times do |i|
								g.instance_variable_set("@#{res.fields[i]}", r[i])
							end
							games[g.id.to_i] = g
						end
						res.clear

=begin						
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
=end	

						# Type1 区分値取得
						res = db.exec(<<-"SQL")
							SELECT
								game_id, type1_id, name
							FROM
								game_type1s
							WHERE
								id IN (#{game_accounts.keys.join(",")})
						SQL
						
						res.each do |r|
							type1[r[0].to_i] ||= {}
							type1[r[0].to_i][r[1].to_i] = h(r[2])
						end
						res.clear
						
						# 仮想 Type1 区分値取得
						SEG_V[:virtual_type1].each_value do |seg|
							type1.each do |game_id, t|
								t[seg[:value].to_i] = h(seg[:name])
							end
						end
						
					rescue => ex
						res_status = "Status: 500 Server Error\n"
						res_body << "サーバーエラーです。ごめんなさい。\n" unless res_body
						raise ex
					ensure
						db.close  if db
					end

					### キャッシュHTML出力
					
					# リンク 部生成
					link_html = Erubis::Eruby.new(File.read(LINK_ERB_PATH)).result(binding)
					# footer 部生成
					footer_html = Erubis::Eruby.new(File.read(FOOTER_ERB_PATH)).result(binding)
					
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
			ENV['QUERY_STRING']
		].join("\t")
	)
rescue
end

