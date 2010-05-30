/*
 *  kakasi.c -- Kakasi module
 *  Copyright (c) 1999-2002 GOTO Kentaro
 */

#include <string.h>
#include "ruby.h"
#include "libkakasi.h"

#define OPTMAX 1024
#define min(x,y) ((x)<(y) ? (x) : (y))

static char const rcsid[] = 
  "$kNotwork: kakasi.c,v 1.3 2002/09/28 05:21:37 gotoken Exp $"; 

static int dic_closed = 1, len = 0;
static char prev_opt_ptr[OPTMAX];

static VALUE
rb_kakasi_kakasi(obj, opt, src)
    VALUE obj, opt, src;
{
    int argc = 0, i = 0;
    char **argv, **opts;
    char *buf, *opt_ptr, *t;
    VALUE dst;

    Check_Type(src, T_STRING);

    /* return "" immediately if source str is empty */
    if (RSTRING_LEN(src) == 0)
	return rb_str_new2("");

    Check_Type(opt, T_STRING);

     /* initialize kakasi iff opt != previous opt */
    if (0 == len || 0 != strncmp(RSTRING_PTR(opt), prev_opt_ptr, 
				 min(RSTRING_LEN(opt), len))) {
	strncpy(prev_opt_ptr, RSTRING_PTR(opt), RSTRING_LEN(opt));
	len = RSTRING_LEN(opt); 

	if (len + 1 > OPTMAX) {
	    rb_raise(rb_eArgError, "too long 1st arg (should be < 1023)");
	}

	if (!dic_closed) {
	    kakasi_close_kanwadict();
	    dic_closed = 1;
	}

	argv = opts = ALLOCA_N(char*, RSTRING_LEN(opt));
	*opts++ = "kakasi";
	argc++;

	opt_ptr = ALLOCA_N(char, 1 + RSTRING_LEN(opt));
	strncpy(opt_ptr, RSTRING_PTR(opt), RSTRING_LEN(opt));
	opt_ptr[RSTRING_LEN(opt)] = '\0';

	if (*opts++ = strtok(opt_ptr, " \t")) {
	    argc++;
	    while (t = strtok(NULL, " \t")) {
		*opts++ = t;
		argc++;
	    }
	}
	
	if (0 != kakasi_getopt_argv(argc, argv))
	    rb_raise(rb_eRuntimeError, "failed to initialize kakasi");
	dic_closed = 0;
    }

    dst = rb_str_new2("");
    while (i < RSTRING_LEN(src)) {
      if (*(RSTRING_PTR(src)+ i) != '\0') {
	buf = kakasi_do((RSTRING_PTR(src)+ i));
	rb_str_concat(dst, rb_str_new2(buf));
	if (*buf) free(buf);
	while (*(RSTRING_PTR(src)+ i) != '\0') {
	  i++;
	}
      }
      if (i == RSTRING_LEN(src)) {
	break;
      }
      rb_str_concat(dst, rb_str_new("\0", 1));
      i++;
    }

    return dst;
}

void
Init_kakasi()
{
    VALUE mKakasi = rb_define_module("Kakasi");

    rb_define_module_function(mKakasi, "kakasi", rb_kakasi_kakasi, 2);
    rb_define_const(mKakasi, "KAKASI_VERSION", rb_str_new2("2002-09-28"));
}
