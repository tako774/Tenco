#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### アカウントタグ削除 API ###
	REVISION = 'R0.01'
	DEBUG = false

	$LOAD_PATH.unshift '../common'
	$LOAD_PATH.unshift '../entity'

	require 'kconv'
	require 'yaml'
	require 'time'
	require 'logger'
	require 'utils'
	require 'setting'
		
	# 設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']

	# ログファイルパス
	LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "../log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

	# HTTP/HTTPSレスポンス文字列
	res_status = nil
	res_header = ''
	res_body = ''

	# ログ開始
	log = Logger.new(LOG_PATH)
	log.level = Logger::DEBUG

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


if ENV['REQUEST_METHOD'] == 'POST' then
	begin
		query = {} # クエリストリング
		source = nil # POSTデータ
		db = nil   # DB接続 
		
		# バリデーション用定数
		MAX_POST_DATA_BYTES = 1000; # 最大受付ポストデータサイズ
		ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
		
		account_name = nil # アカウント名
		tag_id = nil # タグID
		account = nil # アカウント情報
		
		# ポストデータ取得
		if ENV['CONTENT_LENGTH'].to_i > MAX_POST_DATA_BYTES then
			res_status = "Status: 400 Bad Request\n"
			res_body = "ポストデータサイズが大きすぎます\nPost data size is too large.\n"
			raise "ポストデータサイズが大きすぎます"
		end
		source = STDIN.read(ENV['CONTENT_LENGTH'].to_i)
		
		# 入力データ分解
		query = parse_query_str(source)
		
		# 入力バリデーション
		unless (
			query['account_name'] and
			query['account_name'] =~ ACCOUNT_NAME_REGEX
			query['tag_name'] and
			query['tag_name'] != ''
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力データが正しくありません\ninput data validation error.\n"
			raise "input data validation error."
		end

		unless (
			Kconv.isutf8(query['tag_name'])
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力されたタグの文字コードがUTF8ではないようです"
			raise "input tag_name char code validation error."
		end
		
		# 値設定
		account_name = query['account_name']
		tag_name = query['tag_name']
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		
		# トランザクション開始
		db.exec("BEGIN TRANSACTION;")
							
		# アカウント情報取得
		require 'Account'
		res = db.exec(<<-"SQL")
			SELECT
				id, name, data_password, show_ratings_flag, allow_edit_profile
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
		
		if account.allow_edit_profile.to_i == 0 then
			res_status = "Status: 400 Bad Request\n"
			res_body = "プロファイル編集は不許可設定です\n"
			raise "プロファイル編集は不許可"
		end
		
		# アカウント・タグ情報削除
		res = db.exec(<<-"SQL")
			DELETE FROM
				account_tags at
			WHERE
				at.account_id = #{account.id.to_i} AND
				CASE
					WHEN at.tag_disp_name IS NULL THEN (
						SELECT
							name
						FROM
							tags t
						WHERE
							t.id = at.tag_id
						)
					ELSE at.tag_disp_name
				END = #{s tag_name}
			RETURNING at.tag_id
		SQL

		if (res.num_tuples != 1) then
			res.clear
			res_status = "Status: 409 Conflict\n" 
			res_body << "指定されたアカウントタグ情報は存在しないか、すでに削除されています。\n"
			raise "account tag not already deleted"
		else
			tag_id = res[0][0].to_i
			res.clear
		end
		
		# タグ表示代表名更新・タグ情報削除
		begin
			res = db.exec(<<-"SQL")
				SELECT
				  COALESCE(at1.tag_disp_name, t1.name) AS rep_disp_name,
				  COUNT(at1.id) AS cnt
				FROM
				  account_tags at1,
				  tags t1
				WHERE
				  t1.id = #{tag_id.to_i}
				  AND at1.tag_id = #{tag_id.to_i}
				GROUP BY
				  COALESCE(at1.tag_disp_name, t1.name)
				ORDER BY
				  cnt DESC
				LIMIT 1
			SQL
			
			if (res.num_tuples == 1) then
				rep_disp_name = res[0][0].to_s
				res.clear
				
				res = db.exec(<<-"SQL")
					UPDATE
					  tags
					SET
					  rep_disp_name = 
						CASE
						  WHEN name = #{s rep_disp_name} THEN NULL
						  ELSE #{s rep_disp_name}
						END,
					  updated_at = CURRENT_TIMESTAMP,
					  lock_version = lock_version + 1
					WHERE
					  id = #{tag_id.to_i}
					  AND (
						rep_disp_name != #{s rep_disp_name}
						OR (
						  rep_disp_name IS NULL
						  AND name != #{s rep_disp_name}
						)
					  )
				SQL
				
				res.clear
			else
				res.clear
				
				res = db.exec(<<-"SQL")
					DELETE FROM
					  tags
					WHERE
					  id = #{tag_id.to_i}
					RETURNING *
				SQL

				if (res.num_tuples != 1) then
					res.clear
					res_status = "Status: 409 Conflict\n" 
					res_body << "指定されたタグ情報は存在しないか、すでに削除されています。\n"
					raise "tag not already deleted"
				end
				
				res.clear
			end
			
		rescue => ex
			res_status = "Status: 409 Conflict\n" 
			res_body << "タグ表示代表名の更新またはタグ情報の削除に失敗しました。\n"
			res_body << "サーバーエラーです。ごめんなさい。\n"
			raise ex
		end		
		# トランザクション終了
		db.exec("COMMIT;")						
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	rescue => ex
		unless res_status then
			res_status ||= "Status: 500 Internal Server Error\n" 
			res_body << "タグ情報の削除に失敗しました。サーバーエラーです。\n"
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
		res_body = "#{account_name} アカウントの指定されたタグを削除しました"
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
