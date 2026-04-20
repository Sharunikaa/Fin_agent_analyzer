import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDocuments, getDocumentDetails } from '../services/api';
import { FileText, Calendar, Building2, Layers, Table, ChevronRight, Loader2 } from 'lucide-react';

const DocumentExplorer = () => {
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);

  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: getDocuments,
  });

  const { data: docDetails, isLoading: isLoadingDetails } = useQuery({
    queryKey: ['document', selectedDoc],
    queryFn: () => getDocumentDetails(selectedDoc!),
    enabled: !!selectedDoc,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Document Explorer</h2>
        <p className="mt-1 text-sm text-gray-500">
          Browse and explore uploaded financial documents
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Document List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="text-sm font-medium text-gray-900">Documents ({documents?.length || 0})</h3>
            </div>
            
            <div className="divide-y divide-gray-200">
              {isLoading ? (
                <div className="p-8 text-center">
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400 mx-auto" />
                </div>
              ) : documents && documents.length > 0 ? (
                documents.map((doc) => (
                  <button
                    key={doc.doc_id}
                    onClick={() => setSelectedDoc(doc.doc_id)}
                    className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors ${
                      selectedDoc === doc.doc_id ? 'bg-primary-50' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2">
                          <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900 truncate">
                            {doc.company}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center space-x-2 text-xs text-gray-500">
                          <span>{doc.year}</span>
                          <span>•</span>
                          <span>{doc.doc_type}</span>
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    </div>
                  </button>
                ))
              ) : (
                <div className="p-8 text-center text-sm text-gray-500">
                  No documents found
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Document Details */}
        <div className="lg:col-span-2">
          {selectedDoc && docDetails ? (
            <div className="space-y-6">
              {/* Metadata */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Document Information</h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-start space-x-3">
                    <Building2 className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      <div className="text-xs text-gray-500">Company</div>
                      <div className="text-sm font-medium text-gray-900">{docDetails.company}</div>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      <div className="text-xs text-gray-500">Year</div>
                      <div className="text-sm font-medium text-gray-900">{docDetails.year}</div>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <FileText className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      <div className="text-xs text-gray-500">Document Type</div>
                      <div className="text-sm font-medium text-gray-900">{docDetails.doc_type}</div>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      <div className="text-xs text-gray-500">Filing Date</div>
                      <div className="text-sm font-medium text-gray-900">{docDetails.filing_date}</div>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <Layers className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      <div className="text-xs text-gray-500">Pages</div>
                      <div className="text-sm font-medium text-gray-900">{docDetails.pages}</div>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <Table className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      <div className="text-xs text-gray-500">Tables</div>
                      <div className="text-sm font-medium text-gray-900">{docDetails.tables}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Sections */}
              {docDetails.sections && docDetails.sections.length > 0 && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200">
                  <div className="px-6 py-4 border-b border-gray-200">
                    <h3 className="text-lg font-medium text-gray-900">
                      Sections ({docDetails.sections.length})
                    </h3>
                  </div>
                  
                  <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
                    {docDetails.sections.map((section: any, idx: number) => (
                      <div key={idx} className="px-6 py-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-900">
                            {section.section_type.replace(/_/g, ' ').toUpperCase()}
                          </span>
                          <span className="text-xs text-gray-500">
                            Page {section.page_num}
                          </span>
                        </div>
                        {section.content && (
                          <p className="mt-1 text-xs text-gray-600 line-clamp-2">
                            {section.content.substring(0, 150)}...
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tables */}
              {docDetails.tables_summary && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Tables Summary</h3>
                  
                  <div className="grid grid-cols-3 gap-4">
                    {Object.entries(docDetails.tables_summary).map(([type, count]) => (
                      <div key={type} className="text-center p-4 bg-gray-50 rounded-lg">
                        <div className="text-2xl font-bold text-gray-900">{count as number}</div>
                        <div className="text-xs text-gray-500 mt-1 capitalize">
                          {type.replace(/_/g, ' ')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : isLoadingDetails ? (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
              <Loader2 className="w-8 h-8 animate-spin text-gray-400 mx-auto" />
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No document selected</h3>
              <p className="text-sm text-gray-500">
                Select a document from the list to view details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentExplorer;
