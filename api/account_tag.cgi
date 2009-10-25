#!/usr/bin/ruby

# 開始時刻
now = Time.now

### アカウントタグ情報 API ###
REVISION = 'R0.02'
DEBUG = false

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'

require 'rexml/document'
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
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# バリデーション用定数
TAG_NAME_LENGTH_MIN = 2
TAG_NAME_LENGTH_MAX = 20
ACCOUNT_TAG_COUNT_MAX = 10

# HTTP/HTTPSレスポンス文字列
res_status = nil
res_header = ''
res_body = ''

# ログ開始
log = Logger.new(LOG_PATH)
log.level = Logger::DEBUG

if ENV['REQUEST_METHOD'] == 'POST' then
	begin
		query = {} # クエリストリング
		source = nil # POSTデータ
		db = nil   # DB接続 
		account_name = nil # アカウント名
		tag_name = nil # タグ名、タグ表示名を正規化済み
		tag_display_name = nil # タグ表示名
		tag_name_length = nil # タグ名の長さ
		rep_disp_name = nil # タグ代表表示名
		MAX_POST_DATA_BYTES = 1000; # 最大受付ポストデータサイズ
		
		account = nil # アカウント情報
		tag_id = nil # タグID
		
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
			query['account_name'] != '' and
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
		tag_disp_name = query['tag_name']
		tag_name = str_norm(tag_disp_name)
		
		if (tag_name =~ /\s/) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "タグ名にはスペース・タグ・改行を含めることは出来ません"
			raise "input tag name validation error."
		end
		
		tag_name_length = query['tag_name'].split(//u).length
		
		unless (
			TAG_NAME_LENGTH_MIN <= tag_name_length and
			tag_name_length <= TAG_NAME_LENGTH_MAX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "登録できるタグの長さは#{TAG_NAME_LENGTH_MIN}文字以上#{TAG_NAME_LENGTH_MAX}文字以下です"
			raise "input tag name length validation error."
		end
		
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		
		# トランザクション開始
		db.exec("BEGIN TRANSACTION;")
							
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
		
		# タグの保有数をチェック
		res = db.exec(<<-"SQL")
		  SELECT
		    count(id)
		  FROM
		    account_tags
		  WHERE
			account_id = #{account.id.to_i}
		SQL
		
		if res[0][0].to_i >= ACCOUNT_TAG_COUNT_MAX then
			res.clear
			res_status = "Status: 400 Bad Request\n"
			res_body = "１アカウントあたり登録可能なタグ数を超えています\n"
			raise "too many tags for an account error."
		end
		
		res.clear
		
		# タグ SELECT or INSERT
		res = db.exec(<<-"SQL")
		  SELECT
		    id
		  FROM
		    tags
		  WHERE
			name = #{s tag_name}
		SQL
		
		if (res.num_tuples == 0) then
			begin
				res = db.exec(<<-"SQL")
				  INSERT INTO
					tags (
						name,
						rep_disp_name
					)
				  VALUES
					(
					  #{s tag_name},
					  #{tag_name == tag_disp_name ? "NULL" : s(tag_disp_name)}
					)
				  RETURNING id
				SQL
			rescue	
				res = db.exec(<<-"SQL")
				  SELECT
					id
				  FROM
					tags
				  WHERE
					name = #{s tag_name}
				SQL
			end
		end
		
		if (res.num_tuples == 1) then
			tag_id = res[0][0].to_i
		else
			res_status = "Status: 409 Conflict\n" 
			res_body << "タグの登録に失敗しました。\n"
			res_body << "他のユーザーと操作が衝突したかもしれません。\n"
			res_body << "ページを読み込みなおして実行してみてください。"
			raise "select/insert tag record error (#{tag_name})"
		end
		
		res.clear
		
		# アカウントタグ情報登録
		begin
			res = db.exec(<<-"SQL")
			  INSERT INTO
				account_tags (
				  account_id,
				  tag_id,
				  tag_disp_name
				)
			  VALUES
				(
				  #{account.id.to_i},
				  #{tag_id.to_i},
				  #{tag_name == tag_disp_name ? "NULL" : s(tag_disp_name)}
				)
			  RETURNING id
			SQL
		rescue => ex
			res_status = "Status: 409 Conflict\n" 
			res_body << "アカウントタグの登録に失敗しました。\n"
			res_body << "当該アカウントには、入力されたタグがすでにタグ付けされています\n"
			raise ex
		end
		
		res.clear
		
		# タグ表示代表名更新
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
			end
			
		rescue => ex
			res_status = "Status: 409 Conflict\n" 
			res_body << "タグ表示代表名の更新に失敗しました。\n"
			res_body << "サーバーエラーです。ごめんなさい。\n"
			raise ex
		end
		
		# トランザクション終了
		db.exec("COMMIT;")						
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	rescue => ex
		unless res_status then
			res_status ||= "Status: 500 Internal Server Error\n" 
			res_body << "タグ情報の登録に失敗しました。サーバーエラーです。\n"
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
		res_body = "#{account_name} アカウントに #{tag_disp_name} をタグ付けしました"
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
