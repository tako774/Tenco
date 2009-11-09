/**
*
*  URL encode / decode
*  http://www.webtoolkit.info/
*
**/
var Url={encode:function(b){return escape(this._utf8_encode(b))},decode:function(b){return this._utf8_decode(unescape(b))},_utf8_encode:function(b){b=b.replace(/\r\n/g,"\n");for(var d="",c=0;c<b.length;c++){var a=b.charCodeAt(c);if(a<128)d+=String.fromCharCode(a);else{if(a>127&&a<2048)d+=String.fromCharCode(a>>6|192);else{d+=String.fromCharCode(a>>12|224);d+=String.fromCharCode(a>>6&63|128)}d+=String.fromCharCode(a&63|128)}}return d},_utf8_decode:function(b){for(var d="",c=0,a=c1=c2=0;c<b.length;){a= b.charCodeAt(c);if(a<128){d+=String.fromCharCode(a);c++}else if(a>191&&a<224){c2=b.charCodeAt(c+1);d+=String.fromCharCode((a&31)<<6|c2&63);c+=2}else{c2=b.charCodeAt(c+1);c3=b.charCodeAt(c+2);d+=String.fromCharCode((a&15)<<12|(c2&63)<<6|c3&63);c+=3}}return d}};