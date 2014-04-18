#!/usr/bin/perl

use DBI;
#use strict;

$tid=1;

my $db = DBI->connect("dbi:SQLite:dbname=scores.db","","");

open FILE, "schedule.csv" or die "cannot open file: $!";

$db->do("DELETE FROM games WHERE tid=$tid");


while (<FILE>) {
	($gid,$day,$time,$black,$white)  = split(/,/, $_);
	$add = $db->prepare("INSERT INTO games(tid, gid, day, start_time, black, white) VALUES(?,?,?,?,?,?)");

	$add->execute($tid, $gid, $day, $time, $black, $white);		
}

close($fh);


if ( -e "teams.csv" ) {
	$db->do("DELETE FROM teams WHERE tid=$tid");
	open FILE, "teams.csv" or die "cannot open file: $!";

	while (<FILE>) {
		($team_id,$name,$division) = split(/,/, $_);
		
		$add = $db->prepare("INSERT INTO teams(tid, team_id, name, division) VALUES(?,?,?,?)");
		$add->execute($tid, $team_id, $name, $division);
	}
	close FILE;
}

if ( -e "places.csv" ) {
	$db->do("DELETE FROM places WHERE tid=$tid");
	open FILE, "places.csv" or die "cannot open file: $!";

	while (<FILE>) {
		($place,$game) = split(/,/,$_);
		$add = $db->prepare("INSERT INTO places(tid, place, game) VALUES(?,?,?)");
		$add->execute($tid, $place, $game);	
	}
	
	close FILE;
}

