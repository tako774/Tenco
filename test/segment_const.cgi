#!/usr/bin/ruby

# 開始時刻
now = Time.now

begin

	### 区分値定数ファイル生成 ###
	REVISION = '0.02'
	DEBUG = 1

	$LOAD_PATH.unshift '../common'
	$LOAD_PATH.unshift '../entity'

	require 'kconv'
	require 'yaml'
	require 'time'
	require 'db'

	source = ""

	# ログファイルパス
	LOG_PATH = "../log/#{File::basename(__FILE__)}_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

	# HTTP/HTTPSレスポンス文字列
	res_status = ''
	res_header = ''
	res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
end

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		SEGMENT_CONST_FILE_PATH = '../common/segment_const.rb'
		segments = {}       # 区分
		segment_values = {} # 区分値
		seg_str = nil       # 区分テキスト
		seg_v_str = nil     # 区分値テキスト
		
		# DB接続
		db = DB.getInstance()
		
		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 区分データ取得
		require 'Segment'
		res = db.exec(<<-"SQL")
			SELECT
				*
			FROM
				segments
			ORDER BY
				id
		SQL
		
		res.each do |r|
			entity = Segment.new
			res.num_fields.times do |i|
				entity.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			segments[entity.id.to_i] = entity
		end
		res.clear
		
		# 区分値データ取得
		require 'SegmentValue'
		res = db.exec(<<-"SQL")
			SELECT
				*
			FROM
				segment_values
			ORDER BY
				segment_id, segment_value
		SQL
		
		res.each do |r|
			entity = SegmentValue.new
			res.num_fields.times do |i|
				entity.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			segment_values[entity.segment_id.to_i] ||= []
			segment_values[entity.segment_id.to_i] << entity
		end
		res.clear
		
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
		seg_str = "SEG = {\n#{seg_array.join(',')}\n}\n"
		
		# 区分値ハッシュ文生成
		seg_array = []
		segments.each_value do |s|
			seg_v_array = []
			segment_values[s.id.to_i].each do |sv|
				seg_v_array << <<-"SEG_V".chomp
		:#{sv.ascii_name} => {
			:value => #{sv.segment_value},
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
		seg_v_str = "SEG_V = {\n#{seg_array.join(',')}\n}\n"
		
		File.open(SEGMENT_CONST_FILE_PATH, 'w') do |w|
			w.puts "# 区分値ファイル"
			w.puts "# #{now.strftime('%Y/%m/%d %H:%M:%S')} 生成"
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
		db.close
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
