import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
@Injectable({
  providedIn: 'root'
})
export class RdfConverterService {

  private baseUrl = 'http://localhost:5000';

  constructor(private http: HttpClient) {}

  convertToRDF(csv: File, json: File) {
    const formData = new FormData();
    formData.append('csv', csv);
    formData.append('json', json);
    return this.http.post(this.baseUrl + '/convert', formData, {
      responseType: 'blob'
    });
  }
}
