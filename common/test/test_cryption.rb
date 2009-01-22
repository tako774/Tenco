require 'test/unit'
require '../cryption'
require 'kconv'

class Test_Cryption < Test::Unit::TestCase
	def setup
		@str = ["abce1234", "ウィンドウ関数①", "a\tv"]
	end

	# def teardown
	# end
	
	def test_encrypt_decrypt_many_times
		puts "---- test_encrypt_decrypt_many_times"
		@str.each do |s|
			200.times do |i|
				print "." if i % 100 == 0
				enc_str = Cryption.encrypt(s)
				dec_str = Cryption.decrypt(enc_str)
			
				assert_equal(s, dec_str)
			end
		end
		puts
	end
	
	def test_decrypt_base64
		puts "---- test_decrypt_base64"
		str = <<-STR
やまにのぼつ
かわに
ふ。

abcd


		STR
		enc_str = <<-STR
U2FsdGVkX1+UOvA/5SHS9qH7rCV5cYQfQ374aRLert+XhjXer+f0Sr5zLsFdfoV4
SjQMJVkDia3JgL9+sWXL2g==
		STR
		
		puts str.kconv(Kconv::SJIS, Kconv::UTF8)
		puts enc_str
		
		dec_str = Cryption.decrypt_base64(enc_str)
		puts dec_str.kconv(Kconv::SJIS, Kconv::UTF8)
		puts
		
		assert_equal(str, dec_str)
		puts
	end

	def test_encrypt_decrypt_base64
		puts "---- test_encrypt_decrypt_base64"
		@str.each do |s|		
			enc_str = Cryption.encrypt_base64(s)
			puts enc_str
			
			dec_str = Cryption.decrypt_base64(enc_str)
			puts dec_str.kconv(Kconv::SJIS, Kconv::UTF8)
			puts
			
			assert_equal(s, dec_str)
		end
		puts
	end
	
	def test_encrypt_decrypt_base64_many_times
		puts "---- test_encrypt_decrypt_base64_many_times"
		@str.each do |s|
			5000.times do |i|
				print "." if i % 100 == 0
				enc_str = Cryption.encrypt_base64(s)
				dec_str = Cryption.decrypt_base64(enc_str)
			
				assert_equal(s, dec_str)
			end
		end
		puts
	end
end

