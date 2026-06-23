-- 사용: osascript send_imessage.applescript "수신자(번호/AppleID)" "메시지본문"
-- iMessage로 전송. 수신자가 iMessage 사용 불가면 오류 발생(상위에서 처리).
on run argv
	set targetId to item 1 of argv
	set targetMessage to item 2 of argv
	tell application "Messages"
		set targetService to 1st service whose service type = iMessage
		set targetBuddy to buddy targetId of targetService
		send targetMessage to targetBuddy
	end tell
end run
