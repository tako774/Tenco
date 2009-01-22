#!/usr/bin/ruby

# 開始時刻
now = Time.now

### アカウントI/F API ###
REVISION = 'R0.04'

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'

require 'rexml/document'
require 'kconv'
require 'yaml'
require 'time'
require 'logger'

# ログファイルパス
LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# バリデーション用定数
ACCOUNT_NAME_BYTE_MIN = 1
ACCOUNT_NAME_BYTE_MAX = 32
ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
ACCOUNT_PASSWORD_BYTE_MIN = 4
ACCOUNT_PASSWORD_BYTE_MAX = 16
ACCOUNT_MAIL_ADDRESS_BYTE_MAX = 256
ACCOUNT_MAIL_ADDRESS_REGEX = /\A[\x01-\x7F]+@(([-a-z0-9]+\.)*[a-z]+|\[\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\])\z/

# URL
WEB_SERVER_HOST = 'tenco.xrea.jp'
GAME_ID = '1'

# HTTP/HTTPSレスポンス文字列
res_status = nil
res_header = ''
res_body = ''

# ログ開始
log = Logger.new(LOG_PATH)
log.level = Logger::DEBUG

if ENV['REQUEST_METHOD'] == 'POST' then
	begin
		# 受信XMLデータをパース
		source = STDIN.read(ENV['CONTENT_LENGTH'].to_i)
		input_xml = REXML::Document.new(source)

		account_name = input_xml.elements['account/name'].text
		account_password = input_xml.elements['account/password'].text
		account_mail_address = input_xml.elements['account/mail_address'].text || ''
		
		# バリデーション
		unless (
			account_name =~ ACCOUNT_NAME_REGEX and 
			account_name.length >= ACCOUNT_NAME_BYTE_MIN and 
			account_name.length <= ACCOUNT_NAME_BYTE_MAX and
			account_password.length >= ACCOUNT_PASSWORD_BYTE_MIN and 
			account_password.length <= ACCOUNT_PASSWORD_BYTE_MAX and
			account_password != account_name and # アカウント名とパスワードが一緒ならはじく
			(
				account_mail_address == '' or (
					account_mail_address =~ ACCOUNT_MAIL_ADDRESS_REGEX and
					account_mail_address.length <= ACCOUNT_MAIL_ADDRESS_BYTE_MAX
				)
			)
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body << "アカウントの新規登録に失敗しました。再登録をお願いします。\n"
			res_body << "・アカウント名の使用可能文字は、半角英数とアンダースコア_のみです\n"
			res_body << "・アカウント名の長さは、#{ACCOUNT_NAME_BYTE_MIN}バイト以上#{ACCOUNT_NAME_BYTE_MAX}バイト以内に制限しています\n"
			res_body << "・パスワードの長さは、#{ACCOUNT_PASSWORD_BYTE_MIN}バイト以上#{ACCOUNT_PASSWORD_BYTE_MAX}バイト以内に制限しています\n"
			res_body << "・パスワードとアカウント名は、別の文字列にしてください。\n"
			res_body << "・メールアドレスは正しい形式で入力してください。\n"
			res_body << "・メールアドレスの長さは、#{ACCOUNT_MAIL_ADDRESS_BYTE_MAX}バイト以内に制限しています\n"
			raise "アカウントの新規登録に失敗しました。入力値バリデーションエラー"
		end
		
		# DB接続
		require 'db'
		db = DB.getInstance
		
		# アカウント新規登録
		require 'authentication'
		begin
			Authentication.register(account_name, account_password, account_mail_address)
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body = "アカウントの新規登録に失敗しました。別のアカウント名で登録してください。\n"
			raise ex
		end
		
	rescue => ex
		unless res_status then
			res_status = "Status: 500 Internal Server Error\n" 
			res_body << "アカウントの新規登録に失敗しました。サーバーエラーです。\n"
			res_body << "サーバーが不調かもしれません。。。時間をおいてやり直してください。\n"
		end
			File.open(ERROR_LOG_PATH, 'a') do |err_log|
				err_log.puts "#{DateTime.now.to_s} account.cgi" 
				err_log.puts source
				err_log.puts ex.to_s
				err_log.puts ex.backtrace.join("\n").to_s
				err_log.puts
			end
	else
		res_status = "Status: 200 OK\n" unless res_status
		
		res_body = "#{account_name}さんのアカウントを登録しました！\n"
		res_body << "レーティング情報のURLは以下になります\n"
		# res_body << "緋想天全体の情報ページ：http://#{WEB_SERVER_HOST}/game/#{GAME_ID}/ （作成中）\n"
		res_body << "レーティング情報ページ（#{account_name}さん用）：http://#{WEB_SERVER_HOST}/game/#{GAME_ID}/account/#{account_name}/ （α版）\n"
		res_body << "管理用ページ（予定）：http://#{WEB_SERVER_HOST}/account/#{account_name}/manage\n"
	ensure
		# DB切断
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

# HTTP レスポンス送信
res_status = "Status: 500 Internal Server Error\n" unless res_status
res_header << "content-type:text/plain; charset=utf-8\n"
print res_status
print res_header
print "\n"
print res_body

# ログ記録
begin
	times = Process.times
	log.debug(
		[
			File::basename(__FILE__),
			REVISION,
			Time.now - now,
			times.utime + times.stime,
			times.utime,
			times.stime,
			times.cutime,
			times.cstime,
			ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99]
		].join("\t")
	)
rescue
end

exit
