/**
 *  author:		Timothy Groves - http://www.brandspankingnew.net
 *	version:	1.3 - 2006-11-02
 *				1.2 - 2006-11-01
 *				1.1 - 2006-09-29
 *				1.0 - 2006-09-25
 *
 *	requires:	nothing
 *
 */

var useBSNns;

if (useBSNns)
{
	if (typeof(bsn) == "undefined")
		bsn = {}
	var _bsn = bsn;
}
else
{
	var _bsn = this;
}





_bsn.Crossfader = function (divs, fadetime, delay )
{	
	this.nAct = -1;
	this.aDivs = divs;
	
	for (var i=0;i<divs.length;i++)
	{
		document.getElementById(divs[i]).style.opacity = 0;
		document.getElementById(divs[i]).style.position = "absolute";
		document.getElementById(divs[i]).style.filter = "alpha(opacity=0)";
		document.getElementById(divs[i]).style.visibility = "hidden";
	}
	
	this.nDur = fadetime;
	this.nDelay = delay;
		
	this._newfade();
}


_bsn.Crossfader.prototype._newfade = function()
{
	if (this.nID1)
		clearInterval(this.nID1);
	
	this.nOldAct = this.nAct;
	this.nAct++;
	if (!this.aDivs[this.nAct])	this.nAct = 0;
	
	if (this.nAct == this.nOldAct)
		return false;
	
	document.getElementById( this.aDivs[this.nAct] ).style.visibility = "visible";
	
	this.nInt = 50;
	this.nTime = 0;
	
	var p=this;
	this.nID2 = setInterval(function() { p._fade() }, this.nInt);
}


_bsn.Crossfader.prototype._fade = function()
{
	this.nTime += this.nInt;
	
	var ieop = Math.round( this._easeInOut(this.nTime, 0, 1, this.nDur) * 100 );
	var op = ieop / 100;
	document.getElementById( this.aDivs[this.nAct] ).style.opacity = op;
	document.getElementById( this.aDivs[this.nAct] ).style.filter = "alpha(opacity="+ieop+")";
	
	if (this.nOldAct > -1)
	{
		document.getElementById( this.aDivs[this.nOldAct] ).style.opacity = 1 - op;
		document.getElementById( this.aDivs[this.nOldAct] ).style.filter = "alpha(opacity="+(100 - ieop)+")";
	}
	
	if (this.nTime == this.nDur)
	{
		clearInterval( this.nID2 );
		
		if (this.nOldAct > -1)
			document.getElementById( this.aDivs[this.nOldAct] ).style.visibility = "hidden";	
		
		var p=this;
		this.nID1 = setInterval(function() { p._newfade() }, this.nDelay);
	}
}



_bsn.Crossfader.prototype._easeInOut = function(t,b,c,d)
{
	return c/2 * (1 - Math.cos(Math.PI*t/d)) + b;
}