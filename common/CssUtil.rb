# -*- coding: utf-8 -*-
### CSS 関連ユーティリティモジュール
require 'less'

module CssUtil

	# LESS コンパイル実行
	def lessc(str, at_rules = nil)
		css = ""
		
		if !at_rules.nil? then
			css << at_rules.to_s
		end

		css << Less.parse(str)
		
		return css
	end
	
	# 指定ファイルの LESS コンパイル実行
	def lessc_file(file_name)
		less_str = ""
		at_rules = ""
		
		File.open(file_name, 'r') do |f|
			while (line = f.gets)
				if line =~ /\A@/ then
					at_rules << line
				else
					less_str << line
				end
			end
		end
		
		lessc(less_str, at_rules)
	end
 	
	# 指定ディレクトリの LESS コンパイル実行
	def lessc_dir(src_dir, dst_dir = nil, ext = "less")
		
		if dst_dir.nil? then
			dst_dir = src_dir
		end
		
		Dir.glob("#{src_dir}/*.#{ext}").each do |file|
			File.open("#{dst_dir}/#{File.basename(file, ".#{ext}")}.css", "wb") do |w|
				w.puts(lessc_file(file))
			end
		end
		
	end
end

include CssUtil
