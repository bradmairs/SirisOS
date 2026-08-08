import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

class KnowledgeNoteSummary {
  const KnowledgeNoteSummary({
    required this.path,
    required this.title,
    required this.modifiedAt,
    required this.sizeBytes,
    required this.tags,
    required this.wikilinks,
    required this.isDailyNote,
  });

  final String path;
  final String title;
  final DateTime modifiedAt;
  final int sizeBytes;
  final List<String> tags;
  final List<String> wikilinks;
  final bool isDailyNote;

  factory KnowledgeNoteSummary.fromJson(Map<String, dynamic> json) => KnowledgeNoteSummary(
        path: json['path'] as String,
        title: json['title'] as String,
        modifiedAt: DateTime.parse(json['modified_at'] as String),
        sizeBytes: (json['size_bytes'] as num).toInt(),
        tags: (json['tags'] as List<dynamic>? ?? const []).whereType<String>().toList(growable: false),
        wikilinks: (json['wikilinks'] as List<dynamic>? ?? const []).whereType<String>().toList(growable: false),
        isDailyNote: json['is_daily_note'] == true,
      );
}

class KnowledgeOverview {
  const KnowledgeOverview({
    required this.available,
    required this.vaultName,
    required this.noteCount,
    required this.recent,
    required this.daily,
  });

  final bool available;
  final String vaultName;
  final int noteCount;
  final List<KnowledgeNoteSummary> recent;
  final List<KnowledgeNoteSummary> daily;

  factory KnowledgeOverview.fromJson(Map<String, dynamic> json) => KnowledgeOverview(
        available: json['available'] == true,
        vaultName: json['vault_name'] as String? ?? 'Knowledge',
        noteCount: (json['note_count'] as num?)?.toInt() ?? 0,
        recent: (json['recent'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(KnowledgeNoteSummary.fromJson)
            .toList(growable: false),
        daily: (json['daily'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(KnowledgeNoteSummary.fromJson)
            .toList(growable: false),
      );
}

class KnowledgeNote extends KnowledgeNoteSummary {
  const KnowledgeNote({
    required super.path,
    required super.title,
    required super.modifiedAt,
    required super.sizeBytes,
    required super.tags,
    required super.wikilinks,
    required super.isDailyNote,
    required this.content,
  });

  final String content;

  factory KnowledgeNote.fromJson(Map<String, dynamic> json) {
    final summary = KnowledgeNoteSummary.fromJson(json);
    return KnowledgeNote(
      path: summary.path,
      title: summary.title,
      modifiedAt: summary.modifiedAt,
      sizeBytes: summary.sizeBytes,
      tags: summary.tags,
      wikilinks: summary.wikilinks,
      isDailyNote: summary.isDailyNote,
      content: json['content'] as String? ?? '',
    );
  }
}

class KnowledgeService {
  Future<KnowledgeOverview> overview() async {
    final response = await http
        .get(Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/overview'), headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Knowledge overview failed (${response.statusCode}).');
    return KnowledgeOverview.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<KnowledgeNoteSummary>> search(String query) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/search').replace(queryParameters: {'query': query});
    final response = await http.get(uri, headers: AuthService.authorizationHeaders).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Knowledge search failed (${response.statusCode}).');
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['hits'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(KnowledgeNoteSummary.fromJson)
        .toList(growable: false);
  }

  Future<KnowledgeNote> note(String path) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/note').replace(queryParameters: {'path': path});
    final response = await http.get(uri, headers: AuthService.authorizationHeaders).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Unable to open note (${response.statusCode}).');
    return KnowledgeNote.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }
}

class KnowledgeServiceException implements Exception {
  const KnowledgeServiceException(this.message);
  final String message;
  @override
  String toString() => message;
}
