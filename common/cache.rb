require 'memcached'
require 'singleton'
require 'yaml'

class Cache
  include Singleton
  
  def initialize(config_file = "#{File.basename(__FILE__, '.*')}.yaml")
    config = YAML.load_file(config_file)
	
	server = config.delete(:server) 
	@marshal = config.delete(:marshal)
	
	options = config
	
	@cache = Memcached.new(server, options)
  end
  
  def add(key, val, marshal = @marshal)
    @cache.add(key, val, @cache.options[:default_ttl], marshal)
  end
  
  def cas(key, marshal = @marshal, &block)
    @cache.cas(key, @cache.options[:default_ttl], marshal, &block)
  end
  
  def get(keys, marshal = @marshal)
    @cache.get(keys, marshal)
  end

  def replace(key, val, marshal = @marshal)
    @cache.replace(key, val, @cache.options[:default_ttl], marshal)
  end
  
  def set(key, val, marshal = @marshal)
    @cache.set(key, val, @cache.options[:default_ttl], marshal)
  end
  
  def method_missing(method_name, *args, &block)
    @cache.send(method_name, *args, &block)
  end
end

