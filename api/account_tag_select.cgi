#!/usr/bin/ruby

# 開始時刻
now = Time.now

### アカウントタグ取得 API ###
REVISION = 'R0.02'
DEBUG = false

# TOP ディレクトリ
TOP_DIR = '..'

$LOAD_PATH.unshift "#{TOP_DIR}/common"
$LOAD_PATH.unshift "#{TOP_DIR}/entity"

require 'logger'
require 'utils'
require 'setting'
require 'erubis'
include Erubis::XmlHelper

# 設定読み込み
CFG = Setting.new
# TOP ページ URL
TOP_URL = CFG['top_url']
# ログファイルパス
LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"
# キャッシュフォルダパス
CACHE_DIR = "#{TOP_DIR}/cache/eternal/#{File::basename(__FILE__)}"
# キャッシュロックフォルダパス
CACHE_LOCK_DIR = "#{TOP_DIR}/cache/eternal/lock/#{File::basename(__FILE__)}"
# キャッシュをつかったかどうか
is_cache_used = false

# HTTP/HTTPSレスポンス文字列
res_status = nil
res_header = ''
res_body = ""

# ログ開始
logger = Logger.new(LOG_PATH)
logger.level = Logger::DEBUG

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		query = {} # クエリストリング
		source = nil # 受信データ
		db = nil   # DB接続 
		
		account_name = nil # アカウント名
		
		account = nil # アカウント情報
		account_tags = [] # アカウントタグ情報
		
		MAX_POST_DATA_BYTES = 10000; # 最大受付ポストデータサイズ
		
		# クエリデータ取得
		source = ENV['QUERY_STRING']
		
		# 入力データ分解
		query = parse_query_str(source)
		
		# 入力バリデーション
		unless (
			query['account_name'] and
			query['account_name'] != ''
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "入力データが正しくありません\ninput data validation error.\n"
			raise "input data validation error."
		end
		
		# 値設定
		account_name = query['account_name']
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		
		# アカウント情報取得
		require 'Account'
		res = db.exec(<<-"SQL")
			SELECT
				id, name, data_password, show_ratings_flag
			FROM
				accounts
			WHERE
				name = #{s account_name}
				AND del_flag = 0
		SQL
		
		if res.num_tuples != 1 then
			res.clear
			res_status = "Status: 400 Bad Request\n"
			res_body = "該当アカウントは登録されていません\n"
			raise "該当アカウントは登録されていません"
		else
			account = Account.new
			res.num_fields.times do |i|
				account.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
			res.clear
		end
		
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
		
		### XML生成
		require 'rexml/document'
		
		# XML生成
		xml = REXML::Document.new
		xml << REXML::XMLDecl.new('1.0', 'UTF-8')
		
		# account 要素生成
		root = xml.add_element('account_tags')
		
		account_e = root.add_element('account')
		account_e.add_element('name').add_text(h(account.name.to_s))
		
		# tag 要素生成
		account_tags.each do |at|
			tag_e = account_e.add_element('tag')
			tag_e.add_element('id').add_text(at.tag_id.to_i.to_s)
			# CData.new は引数に ']]>' があるとエラーになるが、htmlエスケープしているので発生しない
			tag_e.add_element('display_name').add(REXML::CData.new(h(at.tag_disp_name.to_s)))
#			tag_e.add_element('display_name').add_text(h(at.tag_disp_name.to_s).gsub(/\&/, '&amp;'))
		end
		
		### 結果をセット
		res_status = "Status: 200 OK\n"
		res_header = "content-type:text/xml; charset=utf-8\n"
		res_body = xml.to_s
				
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "サーバーエラーが発生しました。ごめんなさい。（#{now.strftime('%Y/%m/%d %H:%M:%S')}）\n"
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{now.strftime('%Y/%m/%d %H:%M:%S')} #{File::basename(__FILE__)} Rev.#{REVISION}" 
			err_log.puts source
			err_log.puts ex.to_s
			err_log.puts ex.backtrace.join("\n").to_s
			err_log.puts
		end
	ensure
		# DB接続を閉じる
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

begin
# HTTP レスポンス送信
res_status "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n" unless res_header
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
			source
		].join("\t")
	)
rescue
end
