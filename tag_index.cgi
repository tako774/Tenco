#!/usr/bin/ruby

### タグ一覧ページ出力

# 開始時刻
begin
	now = Time.now
	# リビジョン
	REVISION = 'R0.01'
	DEBUG = false

	$LOAD_PATH.unshift './common'
	$LOAD_PATH.unshift './entity'

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

		LINK_ERB_PATH   = "./link.erb"   # リンクERBパス
		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		
		tag_name = nil # タグ名
		
		tags = [] # タグ情報
				
		# クエリストリング分解
		# query = parse_query_str(ENV['QUERY_STRING'])
		
		# バリデーション
		# なし
		
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
						require 'erubis'
						include Erubis::XmlHelper
						
						# DB接続
						db = DB.getInstance
						
						# タグ情報取得
						require 'Tag'
						res = db.exec(<<-"SQL")
							SELECT
							  COALESCE(t.rep_disp_name, t.name) AS rep_disp_name,
							  count(at.id) AS account_num
							FROM
							  tags t,
							  account_tags at
							WHERE
							  at.tag_id = t.id
							GROUP BY
							  t.id, t.name, COALESCE(t.rep_disp_name, t.name)
							ORDER BY 
							  account_num DESC, rep_disp_name
						SQL
						
						res.each do |r|
							tag = Tag.new
							res.num_fields.times do |i|
								tag.instance_variable_set("@#{res.fields[i]}", r[i])
							end
							if hide_ng_words(tag.rep_disp_name.to_s) == tag.rep_disp_name.to_s then
								tags << tag
							end
						end
						res.clear	
						
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

