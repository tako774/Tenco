#!/usr/bin/ruby
# -*- coding: utf-8 -*-

# 開始時刻
now = Time.now

### Glicko Ratings 更新 (ファイル入力) ###
REVISION = '0.03'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'
$LOAD_PATH.unshift '../dao'

require 'kconv'
require 'yaml'
require 'time'

require 'db'
require 'utils'
include Utils

source = ""

# DB設定
DB_USER = 'pgsql'
DB_NAME = 'tenco'
PSQL = '/usr/local/pgsql/bin/psql'

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# データファイルディレクトリ
DATA_DIR = "../dat/ratings"

# テンポラリファイルディレクトリ
TMP_DIR = "./tmp"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

begin
	# 設定
	games = nil # レート計算対象ゲーム情報
	
	# DB接続
	db = DB.getInstance()
	# db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	games = game_dao.get_rating_targets
	
	res_body << "batch target games selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# ゲームIDごとにレート計算実行
	games.each do |game|
		res_body << "★GAME_ID:#{game.id} の処理\n"
		
		data_file = "#{DATA_DIR}/#{game.id}"
		script_file = "#{TMP_DIR}/#{File::basename(__FILE__)}_#{game.id}.sql"
		
		# データロード用SQLファイル作成
		File.open(script_file, "w") do |io|
			io.puts(<<-"SQL")
/* 一時テーブル作成 */
CREATE TEMP TABLE
  temp_game_account_ratings
(
  account_id integer,
  type1_id integer,
  rating real,
  ratings_deviation real,
  matched_accounts integer,
  match_counts integer
)
WITH (
  OIDS=FALSE
);

/* レート情報をファイルからロード */
COPY temp_game_account_ratings
(
  account_id,
  type1_id,
  rating,
  ratings_deviation,
  matched_accounts,
  match_counts
)
FROM
  '#{File.expand_path(data_file)}'
WITH
  (FORMAT 'csv')
;

/* UPDATE */  
UPDATE
  game_account_ratings gar
SET
  rating = tmp.rating,
  ratings_deviation = tmp.ratings_deviation,
  matched_accounts = tmp.matched_accounts,
  match_counts = tmp.match_counts,
  updated_at = CURRENT_TIMESTAMP,
  lock_version = lock_version + 1
FROM
  temp_game_account_ratings tmp
WHERE
  gar.game_id = #{game.id}
  AND gar.account_id = tmp.account_id
  AND gar.type1_id = tmp.type1_id
;

/* INSERT */  
INSERT INTO
  game_account_ratings (
  game_id,
  account_id,
  type1_id,
  rating,
  ratings_deviation,
  matched_accounts,
  match_counts
)
SELECT
  #{game.id},
  account_id,
  type1_id,
  rating,
  ratings_deviation,
  matched_accounts,
  match_counts
FROM
  temp_game_account_ratings tmp
WHERE
  NOT EXISTS (
    SELECT
      1
    FROM
      game_account_ratings gar
    WHERE
	  gar.game_id = #{game.id}
  AND gar.account_id = tmp.account_id
  AND gar.type1_id = tmp.type1_id
)
;

/* 一時テーブル削除 */
DROP TABLE
  temp_game_account_ratings
;
			SQL
		end
		
		res_body << "SQL script generated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		begin
			exec_command = "#{PSQL} -U #{DB_USER} -d #{DB_NAME} -f #{script_file}"
			res_body << "> #{exec_command}\n"
			res_body << `#{exec_command}`
			unless $?.success? then
				res_body << "レーティング情報保存時にエラーが発生しました。\n"
				raise "レーティング情報保存コマンド実行時エラー\n#{exec_command}"
			end
		rescue => ex
			res_status = "Status: 500 Server Error\n"
			res_body << "レーティング情報保存コマンドが実行できませんでした。\n#{exec_command}\n"
			raise ex
		end
		
		res_body << "rating results stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	end
	
	# コミット
	# db.exec("COMMIT")
	# res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body << "レーティング保存時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
	File.open(ERROR_LOG_PATH, 'a') do |log|
		log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
		log.puts source
		log.puts ex.to_s
		log.puts ex.backtrace.join("\n").to_s
		log.puts
	end
else
	res_status = "Status: 200 OK\n" unless res_status
	res_body << "レーティング情報保存正常終了。\n"
ensure
	# DB接続を閉じる
	db.close if db
end

# 実行時間
times = Process.times
res_body << "実行時間 #{Time.now - now}秒, CPU時間 #{times.utime + times.stime}秒\n"
	
# HTTP レスポンス送信
res_status = "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n"
if ENV['REQUEST_METHOD'] == 'GET' then
	print res_status
	print res_header
	print "\n"
end
print res_body

# ログ書き込み
File.open(LOG_PATH, 'a') do |log|
	log.puts "#{now.iso8601} #{File::basename(__FILE__)} Rev.#{REVISION}"
	log.puts "Total Time: #{Time.now - now}"
	log.puts res_status
	log.puts res_header
	log.puts "\n"
	log.puts res_body
	log.puts "----"
end
  
exit
