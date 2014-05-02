#!/usr/bin/ruby

# 開始時刻
now = Time.now

### 区分値定数ファイル生成 ###
REVISION = '0.01'
DEBUG = 1

$LOAD_PATH.unshift '../common'

require 'rubygems'
require 'active_record'
require 'kconv'
require 'yaml'
require 'time'

source = ""

# ログファイルパス
LOG_PATH = "../log/#{File::basename(__FILE__)}_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/#{File::basename(__FILE__)}_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		SEGMENT_CONST_FILE_PATH = '../common/pov_class_const.rb'
		segments = {}       # 区分
		segment_values = {} # 区分値
		seg_str = nil       # 区分テキスト
		seg_v_str = nil     # 区分値テキスト
		
		# DB設定ファイル読み込み
		config_file = '../../../config/database.yaml'
		config = YAML.load_file(config_file)

		# DB接続
		ActiveRecord::Base.establish_connection(
		  :adapter  => config['adapter'],
		  :host     => config['host'],
		  :username => config['username'],
		  :password => config['password'],
		  :database => config['database']
		)
		
		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 区分データ取得
		require 'GamePov'
		GamePov.find(:all, :order => 'id').each do |record|
			segments[record.id] = record
		end
		
		# 区分値データ取得
		require 'GamePovClass'
		GamePovClass.find(:all, :order => 'game_pov_id, value').each do |record|
			segment_values[record.game_pov_id] ||= []
			segment_values[record.game_pov_id] << record
		end
		
		res_body << "区分・区分値取得。\n"
		res_body << "game_povs/segment_pov_classes selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		
		# 区分ハッシュ文生成
		seg_array = []
		segments.each_value do |s|
			seg_array << <<-"SEG".chomp
	# #{s.name}(#{s.id})
	:#{s.ascii_name} => {
		:id => #{s.id},
		:name => '#{s.name}'
	}
			SEG
		end
		seg_str = "GAME_POV = {\n#{seg_array.join(',')}\n}\n"
		
		# 区分値ハッシュ文生成
		seg_array = []
		segments.each_value do |s|
			seg_v_array = []
			segment_values[s.id].each do |sv|
				seg_v_array << <<-"SEG_V".chomp
		:#{sv.ascii_name} => {
			:value => #{sv.value},
			:name => '#{sv.name}'
		}
				SEG_V
			end
			seg_array << <<-"SEG".chomp
	# #{s.name}(#{s.id})
	:#{s.ascii_name} => {
#{seg_v_array.join(",\n")}
	}
			SEG
		end
		seg_v_str = "GAME_POV_CLASS = {\n#{seg_array.join(',')}\n}\n"
		
		File.open(SEGMENT_CONST_FILE_PATH, 'w') do |w|
			w.puts "# 区分値ファイル"
			w.puts "# #{now.strftime('%Y/%m/%d %H:%m:%S')} 生成"
			w.puts
			w.puts seg_str
			w.puts
			w.puts seg_v_str
			w.puts
		end
		
		res_body << "segment const file stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "区分値ファイル作成時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
		File.open(ERROR_LOG_PATH, 'a') do |log|
			log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
			log.puts source
			log.puts ex.to_s
			log.puts ex.backtrace.join("\n").to_s
			log.puts
		end
	else
		res_status = "Status: 200 OK\n" unless res_status
		res_body << "区分値ファイル作成正常終了。\n"
	ensure
		# DB接続を閉じる
		ActiveRecord::Base.remove_connection if ActiveRecord::Base.connected?
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

# 実行時間
times = Process.times
res_body << "実行時間 #{Time.now - now}秒, CPU時間 #{times.utime + times.stime}秒"
	
# HTTP レスポンス送信
res_status "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n"
print res_status
print res_header
print "\n"
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
