#!/usr/bin/perl

use DBI;

my $tid=2;
my %teams = ();

my $db = DBI->connect("dbi:SQLite:dbname=scores.db","","");

$pod=$ARGV[0];

if ( $pod ne "" ) {
	#$db->do("DELETE FROM scores WHERE tid=$tid");
	print "Populating pod $pod\n";
	$q = $db->prepare("SELECT team_id, name FROM teams WHERE tid=?");
	$q->execute($tid);

	while (my $r = $q->fetchrow_hashref) {
		$team_id = $r->{team_id};
		$name = $r->{name};     
		
		$teams{$team_id} = $name
	}

	$q1 = $db->prepare("SELECT black, white, gid FROM games WHERE tid=? AND pod=? AND type='RR'");
	$q1->execute($tid, $pod);

	while ( my $r = $q1->fetchrow_hashref){
		$black = $r->{black};
		$white = $r->{white};
		$gid = $r->{gid};
	
		if ($black =~ m/^T(\d+)$/ ) {
			$black_tid = $1
		}

		if ($white =~ m/^T(\d+)$/ ) {
			$white_tid = $1
		}
	
		if ($black =~ m/^([bdegz])(\d+)$/ ) {
			$q = $db->prepare("SELECT team_id FROM pods WHERE tid=? AND pod=? AND pod_id=?");
			$q->execute($tid, $1, $2);
			$r = $q->fetchrow_hashref;
			$black_tid = $r->{team_id};
		}

		if ($white =~ m/^([bdegz])(\d+)$/ ) {
			$q = $db->prepare("SELECT team_id FROM pods WHERE tid=? AND pod=? AND pod_id=?");
			$q->execute($tid, $1, $2);
			$r = $q->fetchrow_hashref;
			$white_tid = $r->{team_id};
		}

		$score_b = int(rand(10));
		$score_w = int(rand(10));

		print "Scoring game $gid: $black_tid $score_b - $white_tid $score_w\n";
		$q = $db->prepare("INSERT INTO scores(tid, gid, pod, black_tid, white_tid, score_b, score_w) VALUES(?,?,?,?,?,?,?)");
		$q->execute($tid, $gid, $pod, $black_tid, $white_tid, $score_b, $score_w);
	}	

} else {
	print "Give me a number please\n";
}

$db->disconnect();
exit
