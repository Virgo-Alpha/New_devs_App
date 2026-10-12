import React, { useEffect, useState } from "react";
import { RevenueSummary } from "./RevenueSummary";
import { SecureAPI } from "../lib/secureApi";

interface Property {
  id: string;
  name: string;
  timezone: string;
}

const Dashboard: React.FC = () => {
  const [properties, setProperties] = useState<Property[]>([]);
  const [selectedProperty, setSelectedProperty] = useState("");
  const [selectedPeriod, setSelectedPeriod] = useState("2024-03");
  const [propertiesLoading, setPropertiesLoading] = useState(true);
  const [propertiesError, setPropertiesError] = useState("");

  useEffect(() => {
    const fetchProperties = async () => {
      setPropertiesLoading(true);
      setPropertiesError("");

      try {
        const response = await SecureAPI.getDashboardProperties();
        setProperties(response);
        setSelectedProperty((current) => {
          if (response.some((property: Property) => property.id === current)) {
            return current;
          }
          return response[0]?.id || "";
        });
      } catch (error) {
        console.error(error);
        setPropertiesError("Failed to load properties");
      } finally {
        setPropertiesLoading(false);
      }
    };

    fetchProperties();
  }, []);

  const [year, month] = selectedPeriod.split("-").map(Number);

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">Property Management Dashboard</h1>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <div className="mb-6">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
              <div>
                <h2 className="text-lg lg:text-xl font-medium text-gray-900 mb-2">Revenue Overview</h2>
                <p className="text-sm lg:text-base text-gray-600">
                  Monthly performance insights for your properties
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex flex-col">
                  <label className="text-xs font-medium text-gray-700 mb-1">Reporting Month</label>
                  <input
                    type="month"
                    value={selectedPeriod}
                    onChange={(event) => setSelectedPeriod(event.target.value)}
                    className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                  />
                </div>

                <div className="flex flex-col">
                  <label className="text-xs font-medium text-gray-700 mb-1">Select Property</label>
                  <select
                    value={selectedProperty}
                    onChange={(event) => setSelectedProperty(event.target.value)}
                    disabled={propertiesLoading || properties.length === 0}
                    className="block w-full min-w-[200px] px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm disabled:bg-gray-100"
                  >
                    {properties.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          {propertiesError && (
            <div className="p-4 text-red-500 bg-red-50 rounded-lg">
              {propertiesError}
            </div>
          )}

          {!propertiesError && !propertiesLoading && properties.length === 0 && (
            <div className="p-4 text-gray-500 bg-gray-50 rounded-lg">
              No properties are available for this account.
            </div>
          )}

          {selectedProperty && selectedPeriod && (
            <div className="space-y-6">
              <RevenueSummary
                propertyId={selectedProperty}
                year={year}
                month={month}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
