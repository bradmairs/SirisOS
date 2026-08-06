import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/search_result.dart';
import 'auth_service.dart';

class SearchService {
  SearchService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<List<SirisSearchResult>> search(String query) async {
    final trimmed = query.trim();
    if (trimmed.length < 2) return const [];

    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/search')
        .replace(queryParameters: {'q': trimmed});
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 12));

    if (response.statusCode == 401) {
      throw const SearchServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw SearchServiceException(
        'Search failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const SearchServiceException('Search response was not a list.');
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(SirisSearchResult.fromJson)
        .toList(growable: false);
  }
}

class SearchServiceException implements Exception {
  const SearchServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
