require 'openssl'

PASSWORD = File.read("#{File::dirname(__FILE__)}/../../../config/password.txt")

class Cryption
	VERSION = 'v0.03'
	SHA1_CHAR_LENGTH = 40
	SALT_BYTES = 8
	KEYIVGEN_ITERATION_COUNT = 1

	# 指定された長さの16進数文字列生成
	def self.mk_hex(n)
		hex_str = ""
		n.times do 
			hex_str << "%x" % rand(16)
		end
		return hex_str
	end
	
	# 指定された長さのオクテット文字列生成
	def self.mk_octet_str(n)
		chars = ("A" .. "Z").to_a + ("a" .. "z").to_a + ("0" .. "9").to_a + ["+", "/"]
		return Array.new(n) { chars[rand(chars.length).floor] }.join
	end

	# AES256(CBC)salt有で暗号化 + base64 エンコード
	# 'openssl -e -base64 -aes-256-cbc' で復号化可能
	def self.encrypt_base64 (source, password = PASSWORD)
		if (source == '') then
	 		return ''
		else
			enc = OpenSSL::Cipher::Cipher.new('aes-256-cbc')
			salt = mk_octet_str(SALT_BYTES)
			
			enc.encrypt
			enc.pkcs5_keyivgen(
				password,
				salt,
				KEYIVGEN_ITERATION_COUNT
			)
			enc_str = ["Salted__", "#{salt}", "#{(enc.update(source) + enc.final)}"].pack("a8a8a*")
		  	return [enc_str].pack("m*").to_s
		end
	end

	# base64 デコード + AES256(CBC)salt有で復号化
	# 'openssl -e -base64 -aes-256-cbc' で暗号化したものを復号化可能
	def self.decrypt_base64(source, password = PASSWORD)
		if (source == '') then
	 		return ''
		else
			# Base64 デコード
			enc_str = source.unpack("m*")[0]
			cipher_texts = enc_str.unpack("a8a8a*")
			
			dec = OpenSSL::Cipher::Cipher.new('aes-256-cbc') 
	  		dec.decrypt 
	  		dec.pkcs5_keyivgen(
			     password,
			     cipher_texts[1],                 # salt
			     KEYIVGEN_ITERATION_COUNT         # iteration count
			#    ,OpenSSL::Digest::MD5.new()      # Hash function
			)
	  		return (dec.update(cipher_texts[2]) + dec.final).to_s
	  	end
	end 
	
	# AES256(CBC)salt無しで暗号化 + 16進文字列エンコード
	def self.encrypt (source, password = PASSWORD)
		if (source == '') then
	 		return ''
		else
			enc = OpenSSL::Cipher::Cipher.new('aes-256-cbc')
			enc.encrypt
			enc.pkcs5_keyivgen(password)
		  	return ((enc.update(source) + enc.final).unpack("H*")).to_s
		end
	end

	# 16進文字列デコード + AES256(CBC)salt無しで復号化
	def self.decrypt(data, password = PASSWORD)
		if (data == '') then
	 		return ''
		else
			dec = OpenSSL::Cipher::Cipher.new('aes-256-cbc') 
	  		dec.decrypt 
	  		dec.pkcs5_keyivgen(password)
	  		return ((dec.update(Array.new([data]).pack("H*")) + dec.final)).to_s
	  	end
	end 
	
	# SHA256ハッシュ化
	def self.hash(source)
		OpenSSL::Digest::SHA256.new(source).to_s
	end 

	# クライアントがサーバー送信するときののパスワードハッシュ方式（SHA1）でハッシュ変換
	def self.hash_as_client(raw_password)
		OpenSSL::Digest::SHA1.new(raw_password).to_s
	end
	
	# SHA1済みパスワードを保存用パスワードに変換
	def self.stored_password(password, salt)
		return self.hash(password + salt)
	end
	
	# 生パスワードから保存用パスワード生成
	def self.mk_stored_password(raw_password, salt)
		return self.hash(hash_as_client(raw_password) + salt)
	end
	
	# メールアドレスを保存用パスワードに変換
	def self.stored_mail_address(mail_address, salt)
		return self.hash(mail_address + salt) if mail_address != ''
		return ''
	end 
end
