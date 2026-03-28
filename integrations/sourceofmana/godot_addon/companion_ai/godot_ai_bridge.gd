extends Node
class_name GodotAiBridge
## HTTP bridge to companion API: POST /game/external/decide and /demo-log.

@export var api_base_url: String = "http://127.0.0.1:8000"
@export var bearer_token: String = ""

signal decide_ready(action: String, source: String)
signal decide_failed(error_message: String)
signal demo_log_done()
signal demo_log_failed(error_message: String)

var _http: HTTPRequest
var _pending: String = ""
var _busy: bool = false

func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)


func request_decide(
	game_id: String,
	state: Dictionary,
	actions: PackedStringArray,
	emotion: String = "neutral",
	use_llm: bool = false,
) -> void:
	if _busy:
		decide_failed.emit("busy")
		return
	var payload := {
		"game_id": game_id,
		"state": state,
		"actions": Array(actions),
		"emotion": emotion,
		"use_llm": use_llm,
	}
	_busy = true
	_pending = "decide"
	var headers := PackedStringArray(["Content-Type: application/json"])
	if bearer_token.strip_edges() != "":
		headers.append("Authorization: Bearer %s" % bearer_token.strip_edges())
	var url := "%s/game/external/decide" % api_base_url.rstrip("/")
	var err := _http.request(url, headers, HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		_busy = false
		_pending = ""
		decide_failed.emit("request() failed: %s" % err)


func request_demo_log(game_id: String, state: Dictionary, action: String, meta: Dictionary = {}) -> void:
	if _busy:
		demo_log_failed.emit("busy")
		return
	var payload := {
		"game_id": game_id,
		"state": state,
		"action": action,
		"meta": meta,
	}
	_busy = true
	_pending = "demo"
	var headers := PackedStringArray(["Content-Type: application/json"])
	if bearer_token.strip_edges() != "":
		headers.append("Authorization: Bearer %s" % bearer_token.strip_edges())
	var url := "%s/game/external/demo-log" % api_base_url.rstrip("/")
	var err := _http.request(url, headers, HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		_busy = false
		_pending = ""
		demo_log_failed.emit("request() failed: %s" % err)


func _on_request_completed(_result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_busy = false
	var kind := _pending
	_pending = ""
	var text := body.get_string_from_utf8()
	if response_code != 200:
		var msg := "HTTP %s %s" % [response_code, text]
		if kind == "decide":
			decide_failed.emit(msg)
		else:
			demo_log_failed.emit(msg)
		return
	if kind == "demo":
		demo_log_done.emit()
		return
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY:
		decide_failed.emit("bad JSON")
		return
	var action: String = str(data.get("action", ""))
	var source: String = str(data.get("source", ""))
	decide_ready.emit(action, source)
