import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

enum SirisMemoryClass { fact, preference, episode, decision, observation, conversation }

extension SirisMemoryClassLabel on SirisMemoryClass {
  String get apiValue => name;

  String get label => switch (this) {
        SirisMemoryClass.fact => 'Fact',
        SirisMemoryClass.preference => 'Preference',
        SirisMemoryClass.episode => 'Episode',
        SirisMemoryClass.decision => 'Decision',
        SirisMemoryClass.observation => 'Observation',
        SirisMemoryClass.conversation => 'Conversation',
      };

  static SirisMemoryClass fromApiValue(String value) => SirisMemoryClass.values.firstWhere(
        (item) => item.apiValue == value,
        orElse: () => SirisMemoryClass.fact,
      );
}

class SirisMemoryRecord {
  const SirisMemoryRecord({
    required this.id,
    required this.memoryClass,
    required this.content,
    required this.createdAt,
    this.source,
  });

  final String id;
  final SirisMemoryClass memoryClass;
  final String content;
  final String? source;
  final DateTime createdAt;

  factory SirisMemoryRecord.fromJson(Map<String, dynamic> json) => SirisMemoryRecord(
        id: json['id'] as String,
        memoryClass: SirisMemoryClassLabel.fromApiValue(json['memory_class'] as String),
        content: json['content'] as String,
        source: json['source'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class SirisMemorySuggestion {
  const SirisMemorySuggestion({required this.memoryClass, required this.content});

  factory SirisMemorySuggestion.fromJson(Map<String, dynamic> json) => SirisMemorySuggestion(
        memoryClass: SirisMemoryClassLabel.fromApiValue(json['memory_class'] as String),
        content: json['content'] as String,
      );

  final SirisMemoryClass memoryClass;
  final String content;
}

class SirisMemoryService {
  Future<List<SirisMemoryRecord>> list({SirisMemoryClass? memoryClass}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/siris/memory').replace(
      queryParameters: memoryClass != null ? {'memory_class': memoryClass.apiValue} : null,
    );
    final response = await http
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw SirisMemoryException('Unable to load Siris memory (${response.statusCode}).');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['memory'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(SirisMemoryRecord.fromJson)
        .toList(growable: false);
  }

  Future<SirisMemoryRecord> create({
    required SirisMemoryClass memoryClass,
    required String content,
    String? source,
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/siris/memory'),
          headers: {
            ...AuthService.authorizationHeaders,
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'memory_class': memoryClass.apiValue,
            'content': content,
            if (source != null && source.trim().isNotEmpty) 'source': source.trim(),
          }),
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 201) {
      throw SirisMemoryException('Unable to save memory (${response.statusCode}).');
    }
    return SirisMemoryRecord.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  /// Best-effort: asks the backend to extract candidate memories from one real
  /// chat exchange. Fails open (empty list) on any error -- a suggestion
  /// failure must never surface as an error to someone just trying to chat.
  Future<List<SirisMemorySuggestion>> suggest({
    required String userMessage,
    required String assistantMessage,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('${ApiConfig.baseUrl}/api/v1/siris/memory/suggest'),
            headers: {
              ...AuthService.authorizationHeaders,
              'Content-Type': 'application/json',
            },
            body: jsonEncode({'user_message': userMessage, 'assistant_message': assistantMessage}),
          )
          .timeout(const Duration(seconds: 20));
      if (response.statusCode != 200) return const [];
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      // Growable: the chat screen calls .remove() on this list when the
      // athlete saves or dismisses a suggestion chip.
      return (body['suggestions'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(SirisMemorySuggestion.fromJson)
          .toList();
    } catch (_) {
      return const [];
    }
  }

  Future<void> delete(String id) async {
    final response = await http
        .delete(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/siris/memory/$id'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 204) {
      throw SirisMemoryException('Unable to delete memory (${response.statusCode}).');
    }
  }
}

class SirisMemoryException implements Exception {
  const SirisMemoryException(this.message);
  final String message;

  @override
  String toString() => message;
}
