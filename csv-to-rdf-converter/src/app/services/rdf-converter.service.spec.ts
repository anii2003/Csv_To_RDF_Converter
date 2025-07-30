import { TestBed } from '@angular/core/testing';

import { RdfConverterService } from './rdf-converter.service';

describe('RdfConverterService', () => {
  let service: RdfConverterService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(RdfConverterService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
