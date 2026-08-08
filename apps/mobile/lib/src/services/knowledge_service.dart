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

class KnowledgeFolderSummary {
  const KnowledgeFolderSummary({required this.path, required this.name, required this.noteCount});
  final String path;
  final String name;
  final int noteCount;

  factory KnowledgeFolderSummary.fromJson(Map<String, dynamic> json) => KnowledgeFolderSummary(
        path: json['path'] as String,
        name: json['name'] as String,
        noteCount: (json['note_count'] as num?)?.toInt() ?? 0,
      );
}

class KnowledgeTagSummary {
  const KnowledgeTagSummary({required this.tag, required this.noteCount});
  final String tag;
  final int noteCount;

  factory KnowledgeTagSummary.fromJson(Map<String, dynamic> json) => KnowledgeTagSummary(
        tag: json['tag'] as String,
        noteCount: (json['note_count'] as num?)?.toInt() ?? 0,
      );
}

class KnowledgeBrowse {
  const KnowledgeBrowse({required this.folders, required this.tags});
  final List<KnowledgeFolderSummary> folders;
  final List<KnowledgeTagSummary> tags;

  factory KnowledgeBrowse.fromJson(Map<String, dynamic> json) => KnowledgeBrowse(
        folders: (json['folders'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(KnowledgeFolderSummary.fromJson)
            .toList(growable: false),
        tags: (json['tags'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(KnowledgeTagSummary.fromJson)
            .toList(growable: false),
      );
}

class KnowledgeLinkResolution {
  const KnowledgeLinkResolution({
    required this.target,
    required this.resolved,
    required this.ambiguous,
    this.note,
    required this.candidates,
  });

  final String target;
  final bool resolved;
  final bool ambiguous;
  final KnowledgeNoteSummary? note;
  final List<KnowledgeNoteSummary> candidates;

  factory KnowledgeLinkResolution.fromJson(Map<String, dynamic> json) => KnowledgeLinkResolution(
        target: json['target'] as String? ?? '',
        resolved: json['resolved'] == true,
        ambiguous: json['ambiguous'] == true,
        note: json['note'] is Map<String, dynamic>
            ? KnowledgeNoteSummary.fromJson(json['note'] as Map<String, dynamic>)
            : null,
        candidates: (json['candidates'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(KnowledgeNoteSummary.fromJson)
            .toList(growable: false),
      );
}

class KnowledgeRelatedNote {
  const KnowledgeRelatedNote({required this.note, required this.score, required this.reasons});
  final KnowledgeNoteSummary note;
  final int score;
  final List<String> reasons;

  factory KnowledgeRelatedNote.fromJson(Map<String, dynamic> json) => KnowledgeRelatedNote(
        note: KnowledgeNoteSummary.fromJson(json['note'] as Map<String, dynamic>),
        score: (json['score'] as num?)?.toInt() ?? 0,
        reasons: (json['reasons'] as List<dynamic>? ?? const []).whereType<String>().toList(growable: false),
      );
}

class KnowledgeGraphNode {
  const KnowledgeGraphNode({required this.id, required this.title, required this.center});
  final String id;
  final String title;
  final bool center;

  factory KnowledgeGraphNode.fromJson(Map<String, dynamic> json) => KnowledgeGraphNode(
        id: json['id'] as String,
        title: json['title'] as String,
        center: json['center'] == true,
      );
}

class KnowledgeGraphEdge {
  const KnowledgeGraphEdge({required this.source, required this.target, required this.kind, required this.label});
  final String source;
  final String target;
  final String kind;
  final String label;

  factory KnowledgeGraphEdge.fromJson(Map<String, dynamic> json) => KnowledgeGraphEdge(
        source: json['source'] as String,
        target: json['target'] as String,
        kind: json['kind'] as String,
        label: json['label'] as String,
      );
}

class KnowledgeGraph {
  const KnowledgeGraph({required this.centerPath, required this.nodes, required this.edges});
  final String centerPath;
  final List<KnowledgeGraphNode> nodes;
  final List<KnowledgeGraphEdge> edges;

  factory KnowledgeGraph.fromJson(Map<String, dynamic> json) => KnowledgeGraph(
        centerPath: json['center_path'] as String,
        nodes: (json['nodes'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(KnowledgeGraphNode.fromJson)
            .toList(growable: false),
        edges: (json['edges'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(KnowledgeGraphEdge.fromJson)
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

  Future<KnowledgeBrowse> browse() async {
    final response = await http
        .get(Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/browse'), headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Knowledge browse failed (${response.statusCode}).');
    return KnowledgeBrowse.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<KnowledgeNoteSummary>> contextNotes(String contextId, {int limit = 20}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/context').replace(
      queryParameters: {'context_id': contextId, 'limit': '$limit'},
    );
    final response = await http.get(uri, headers: AuthService.authorizationHeaders).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw KnowledgeServiceException('Knowledge context failed (${response.statusCode}).');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['notes'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(KnowledgeNoteSummary.fromJson)
        .toList(growable: false);
  }

  Future<List<KnowledgeNoteSummary>> search(String query, {String? folder, String? tag}) async {
    final params = <String, String>{'query': query};
    if (folder != null && folder.isNotEmpty) params['folder'] = folder;
    if (tag != null && tag.isNotEmpty) params['tag'] = tag;
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/search').replace(queryParameters: params);
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

  Future<List<KnowledgeNoteSummary>> backlinks(String path) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/backlinks').replace(queryParameters: {'path': path});
    final response = await http.get(uri, headers: AuthService.authorizationHeaders).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Unable to load backlinks (${response.statusCode}).');
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['backlinks'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(KnowledgeNoteSummary.fromJson)
        .toList(growable: false);
  }

  Future<List<KnowledgeRelatedNote>> related(String path) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/related').replace(queryParameters: {'path': path});
    final response = await http.get(uri, headers: AuthService.authorizationHeaders).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Unable to load related notes (${response.statusCode}).');
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['related'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(KnowledgeRelatedNote.fromJson)
        .toList(growable: false);
  }

  Future<KnowledgeGraph> graph(String path) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/graph').replace(queryParameters: {'path': path});
    final response = await http.get(uri, headers: AuthService.authorizationHeaders).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Unable to load note graph (${response.statusCode}).');
    return KnowledgeGraph.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<KnowledgeLinkResolution> resolveLink(String target, {String? sourcePath}) async {
    final params = <String, String>{'target': target};
    if (sourcePath != null && sourcePath.isNotEmpty) params['source_path'] = sourcePath;
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/knowledge/resolve').replace(queryParameters: params);
    final response = await http.get(uri, headers: AuthService.authorizationHeaders).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) throw KnowledgeServiceException('Unable to resolve link (${response.statusCode}).');
    return KnowledgeLinkResolution.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }
}

class KnowledgeServiceException implements Exception {
  const KnowledgeServiceException(this.message);
  final String message;
  @override
  String toString() => message;
}
