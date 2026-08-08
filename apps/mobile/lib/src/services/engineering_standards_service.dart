import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

class EngineeringStandardDocument {
  const EngineeringStandardDocument({
    required this.id,
    required this.title,
    required this.authority,
    required this.filename,
    required this.uploadedAt,
    required this.pages,
    required this.indexed,
    this.reference,
    this.edition,
  });

  final String id;
  final String title;
  final String authority;
  final String? reference;
  final String? edition;
  final String filename;
  final DateTime uploadedAt;
  final int pages;
  final bool indexed;

  factory EngineeringStandardDocument.fromJson(Map<String, dynamic> json) =>
      EngineeringStandardDocument(
        id: json['id'] as String,
        title: json['title'] as String,
        authority: json['authority'] as String,
        reference: json['reference'] as String?,
        edition: json['edition'] as String?,
        filename: json['filename'] as String,
        uploadedAt: DateTime.parse(json['uploaded_at'] as String),
        pages: (json['pages'] as num?)?.toInt() ?? 0,
        indexed: json['indexed'] == true,
      );
}

class EngineeringStandardSearchHit {
  const EngineeringStandardSearchHit({
    required this.document,
    this.page,
    this.snippet,
  });

  final EngineeringStandardDocument document;
  final int? page;
  final String? snippet;

  factory EngineeringStandardSearchHit.fromJson(Map<String, dynamic> json) =>
      EngineeringStandardSearchHit(
        document: EngineeringStandardDocument.fromJson(
          json['document'] as Map<String, dynamic>,
        ),
        page: (json['page'] as num?)?.toInt(),
        snippet: json['snippet'] as String?,
      );
}

class EngineeringStandardPage {
  const EngineeringStandardPage({
    required this.document,
    required this.page,
    required this.text,
    required this.citation,
  });

  final EngineeringStandardDocument document;
  final int page;
  final String text;
  final String citation;

  factory EngineeringStandardPage.fromJson(Map<String, dynamic> json) =>
      EngineeringStandardPage(
        document: EngineeringStandardDocument.fromJson(
          json['document'] as Map<String, dynamic>,
        ),
        page: (json['page'] as num).toInt(),
        text: json['text'] as String? ?? '',
        citation: json['citation'] as String? ?? '',
      );
}

class EngineeringStandardsService {
  Future<List<EngineeringStandardSearchHit>> search({
    String query = '',
    String? authority,
  }) async {
    final params = <String, String>{'query': query};
    if (authority != null && authority.trim().isNotEmpty) {
      params['authority'] = authority.trim();
    }
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/engineering/standards')
        .replace(queryParameters: params);
    final response = await http
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw EngineeringStandardsException('Standards search failed (${response.statusCode}).');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final hits = body['hits'] as List<dynamic>? ?? const [];
    return hits
        .whereType<Map<String, dynamic>>()
        .map(EngineeringStandardSearchHit.fromJson)
        .toList(growable: false);
  }

  Future<EngineeringStandardPage> page({
    required String documentId,
    required int page,
  }) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/api/v1/engineering/standards/$documentId/pages/$page',
    );
    final response = await http
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) {
      throw EngineeringStandardsException('Unable to load standard page (${response.statusCode}).');
    }
    return EngineeringStandardPage.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<EngineeringStandardDocument> uploadPdf({
    required Uint8List bytes,
    required String filename,
    required String title,
    required String authority,
    String? reference,
    String? edition,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('${ApiConfig.baseUrl}/api/v1/engineering/standards'),
    );
    request.headers.addAll(AuthService.authorizationHeaders);
    request.fields['title'] = title.trim();
    request.fields['authority'] = authority.trim();
    if (reference != null && reference.trim().isNotEmpty) {
      request.fields['reference'] = reference.trim();
    }
    if (edition != null && edition.trim().isNotEmpty) {
      request.fields['edition'] = edition.trim();
    }
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: filename,
      ),
    );
    final streamed = await request.send().timeout(const Duration(minutes: 2));
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode != 201) {
      String detail = 'Standards upload failed (${response.statusCode}).';
      try {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        if (decoded['detail'] is String) detail = decoded['detail'] as String;
      } catch (_) {}
      throw EngineeringStandardsException(detail);
    }
    return EngineeringStandardDocument.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}

class EngineeringStandardsException implements Exception {
  const EngineeringStandardsException(this.message);
  final String message;
  @override
  String toString() => message;
}
