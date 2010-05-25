require 'memcached'
require 'singleton'
require 'yaml'

class Cache
  include Singleton
  
  def initialize(config_file = "#{File.basename(__FILE__, '.*')}.yaml")
    config = YAML.load_file(config_file)
	
	server = config[:server]
	config.delete :server 
	
	option = config
	
	@cache = Memcached.new(server, option)
  end
  
  def method_missing(method_name, *args, &block)
    @cache.send(method_name, *args, &block)
  end
end

