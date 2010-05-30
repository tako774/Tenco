#!/usr/bin/ruby

# 開始時刻
now = Time.now

### マッチ済み対戦結果ファイルのマージ ###
# 一方を時間順ソート済みの本体ファイル、
# 他方は未ソートの複数ファイルとし、
# ソート済みの本体ファイルに未ソートのファイルデータをマージする

REVISION = '0.05'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../dao'
$LOAD_PATH.unshift '../entity'

require 'kconv'
require 'yaml'
require 'time'

require 'db'
require 'utils'

source = ""

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# データファイルディレクトリ
DATA_DIR = "../dat/matched_track_records"

# トランデータディレクトリ
TRN_DATA_DIR = "../dat/matched_track_records_trn"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

begin
	# 設定
	CSV_SEPARATOR = ','
	CSV_SEPARATOR_REGEX = /,/o
	
	# DB接続
	db = DB.getInstance()
	db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	game_ids = game_dao.get_batch_target_ids

	res_body << "batch target game_ids selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	# ゲームIDごとに実行
	game_ids.each do |game_id|
		data_file = "#{DATA_DIR}/#{game_id}" # ソート済みファイル出力先パス
		data_temp_file = "#{DATA_DIR}/#{game_id}.temp" # ソート済みファイル出力先一時パス
		trn_files = [] # マージ対象のトランファイル
		trn_data = [] # トランデータ
		
		trn_data_counts = 0 # トランデータ数
		existing_data_counts = 0 # 既存データ数
		merged_data_counts = 0 # マージされたデータ数
		not_merged_data_counts = 0 # マージされなかったデータ数
		
		res_body << "★GAME_ID:#{game_id} の処理\n"
		
		# トランファイル一覧取得
		Dir.glob("#{TRN_DATA_DIR}/#{game_id}_*.dat").each do |trn_file|
			trn_files << trn_file
		end
	
		# トランファイルからデータ取得
		trn_files.each do |file|
			File.open(file, 'rb') do |f| 
				while (line = f.gets) do
					trn_data << line
				end
			end
		end
		
		trn_data_counts = trn_data.length
		
		res_body << "トランデータ #{trn_data_counts} 件を読み込み...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

		# トランデータの重複を削除
		trn_data.uniq!
		res_body << "重複削除対象 #{trn_data_counts - trn_data.length} 件\n" if DEBUG
		
		# トランデータを代表対戦時刻の昇順にソート
		trn_data.sort!
		res_body << "transaction data sorted...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 既存ソート済みファイルとマージしつつファイル出力
		File.open(data_temp_file, 'wb') do |w|
			File.open(data_file, 'rb') do |r|
				while (line = r.gets) do
					while (trn_data.length != 0) do
						if (trn_data[0] < line) then
							w.puts trn_data.shift
							merged_data_counts += 1
							next
						elsif (trn_data[0] == line) then
							trn_data.shift
							not_merged_data_counts += 1
							next
						else
							break
						end
					end
					w.puts line
					existing_data_counts += 1
				end
			end
			w.puts trn_data.join();
			merged_data_counts += trn_data.length
		end

		res_body << "既存データ数 #{existing_data_counts} 件とマージしました\n" if DEBUG		
		
		res_body << "マージ後件数 #{existing_data_counts + merged_data_counts} 件...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		res_body << "重複削除対象　#{not_merged_data_counts} 件...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
				
		# ファイル移動
		File.rename(data_temp_file, data_file)

		res_body << "file output...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# トランデータ削除
		trn_files.each do |trn_file|
			File.unlink trn_file
		end
		
		res_body << "transaction data files deleted...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	end
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body << "マッチ済み対戦結果ファイルのマージ時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
	File.open(ERROR_LOG_PATH, 'a') do |log|
		log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
		log.puts source
		log.puts ex.to_s
		log.puts ex.backtrace.join("\n").to_s
		log.puts
	end
else
	res_status = "Status: 200 OK\n" unless res_status
	res_body << "マッチ済み対戦結果ファイルのマージ正常終了\n"
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
