#!/usr/bin/perl

use DBI;
#use strict;

$tid=8;

my $db = DBI->connect("dbi:SQLite:dbname=../scores.db","","");

$db->do("DELETE FROM SCORES WHERE tid=$tid");

if (-e "schedule.csv") {
	open FILE, "schedule.csv" or die "cannot open file: $!";

	$db->do("DELETE FROM games WHERE tid=$tid");

	$header = <FILE>;

	while (<FILE>) {
		($gid,$day,$time,$pool,$black,$white,$div,$pod,$type,$desc)  = split(/,/, $_);
		chomp $type;
		$type =~ s/^\s+|\s+$//g;
		chomp $desc;
		$desc =~ s/^\s+|\s+$//g;
		$desc =~ s/\r|\n//g;

		if ($time =~ /^\d\:\d\d/) {
			$time="0$time"
		}
		if ($type){
			$add = $db->prepare("INSERT INTO games(tid, gid, day, start_time, pool, black, white, division, pod, type,description) VALUES(?,?,?,?,?,?,?,?,?,?,?)");
			$add->execute($tid, $gid, $day, $time, $pool, $black, $white, $div, $pod, $type,$desc);
		} else{
			$add = $db->prepare("INSERT INTO games(tid, gid, day, start_time, pool, black, white, division, pod) VALUES(?,?,?,?,?,?,?,?,?)");
			$add->execute($tid, $gid, $day, $time, $pool, $black, $white, $division, $pod);
		}
	}

	close($fh);
}

if ( -e "teams.csv" ) {
	$db->do("DELETE FROM teams WHERE tid=$tid");
	open FILE, "teams.csv" or die "cannot open file: $!";

	while (<FILE>) {
		($team_id,$name,$division) = split(/,/, $_);
		chomp $division;
		$division =~ s/^\s+|\s+$//g;
		$add = $db->prepare("INSERT INTO teams(tid, team_id, name, division) VALUES(?,?,?,?)");
		$add->execute($tid, $team_id, $name, $division);
	}
	close FILE;
}

if ( -e "rankings.csv" ) {
	$db->do("DELETE FROM rankings WHERE tid=$tid");
	open FILE, "rankings.csv" or die "cannot open file: $!";

	while (<FILE>) {
		($place,$game,$division) = split(/,/,$_);
		chomp $division;

		$add = $db->prepare("INSERT INTO rankings(tid, place, game, division) VALUES(?,?,?,?)");
		$add->execute($tid, $place, $game, $division);
	}

	close FILE;
}

if ( -e "pods.csv"){
	$db->do("DELETE FROM pods WHERE tid=$tid");

	open FILE, "pods.csv" or die "cannot open file: $!";

	while(<FILE>){
		($team_id,$pod) = split(/,/,$_);
		chomp $pod;
		$pod =~ s/^\r+|\r+$//g;
		$add = $db->prepare("INSERT INTO pods(tid, team_id, pod) VALUES(?,?,?)");
		$add->execute($tid, $team_id, $pod);
	}
	close FILE;
}

if (-e "groups.csv"){
	$db->do("DELETE FROM groups WHERE tid=$tid");

	open FILE, "groups.csv" or die "cannot open file: $!";

	while(<FILE>){
		($group_id,$name) = split(/,/,$_);
		chomp $name;
		$name =~ s/^\r+|\r+$//g;
		$add = $db->prepare("INSERT INTO groups(tid,group_id,name) VALUES(?,?,?)");
		$add->execute($tid,$group_id,$name);
	}
	close FILE;
}
$db->do("DELETE FROM params WHERE tid=$tid");

#$add = $db->prepare("INSERT INTO params(tid, field, val) VALUES(?,?,?)");
#$add->execute($tid,"seeded_pods","0");

#$db->do("update games set division='O' where tid=6;");
