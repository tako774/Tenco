#!/usr/bin/ruby

# 開始時刻
now = Time.now

### マッチ済み対戦結果ファイル出力 ###
REVISION = '0.01'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../dao'

require 'kconv'
require 'yaml'
require 'time'

require 'db'
require 'utils'
include Utils

source = ""

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# データファイルディレクトリ
DATA_DIR = "../dat/matched_track_records"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

begin
	# 設定
	CSV_SEPARATOR = ','
	CSV_SEPARATOR_REGEX = /,/o
	
	# DB接続
	require 'db'
	db = DB.getInstance()
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	game_ids = game_dao.get_batch_target_ids
	
	res_body << "batch target game_ids selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	Dir.mkdir DATA_DIR unless File.directory?(DATA_DIR)

	# ゲームIDごとに実行
	game_ids.each do |game_id|
		str = "" # ファイル出力文字列
		data_file = "#{DATA_DIR}/#{game_id}" # 出力先パス
		
		res_body << "★GAME_ID:#{game_id} の処理\n"
		
		
		res = db.exec(<<-"SQL")
			SELECT
			  EXTRACT(EPOCH FROM rep_timestamp),
			  player1_account_id,
			  player2_account_id,
			  player1_type1_id,
			  player2_type1_id,
			  player1_points,
			  player2_points
			FROM
			  track_records			
			WHERE
				  id > matched_track_record_id
			  AND game_id = #{game_id.to_i}
			ORDER BY
			  rep_timestamp
		SQL
			
		res_body << "matched trackrecords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

		# 出力文字列生成
		res.each do |r|
			str << r.join(CSV_SEPARATOR)
			str << "\n"
		end
				
		# ファイル書き出し
		File.open(data_file, 'wb') do |w|
			w.print str
		end

		res_body << "#{res.num_tuples} 件の対戦結果をファイル出力\n" if DEBUG

		res.clear
	end
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body << "マッチ済み対戦結果ファイル出力時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
	File.open(ERROR_LOG_PATH, 'a') do |log|
		log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
		log.puts source
		log.puts ex.to_s
		log.puts ex.backtrace.join("\n").to_s
		log.puts
	end
else
	res_status = "Status: 200 OK\n" unless res_status
	res_body << "マッチ済み対戦結果ファイル出力正常終了\n"
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
