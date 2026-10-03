package com.gitgalaxy.modernized.ibmwca4z;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.sql.Connection;
import java.sql.Driver;
import java.sql.DriverManager;
import java.sql.DriverPropertyInfo;
import java.sql.SQLException;
import java.sql.SQLFeatureNotSupportedException;
import java.util.Properties;
import java.util.logging.Logger;
import javax.sql.DataSource;
import org.springframework.jdbc.datasource.DataSourceUtils;

/**
 * IBM WCA4Z adapter (tests/tools/ibm_wca4z_port.py): the JDBC driver behind the placeholder URL IBM's generated
 * code connects to, {@code DriverManager.getConnection("endpoint_url")}.
 *
 * <p>It answers that URL, and only that URL, with the connection the harness's Db2 transaction already holds for
 * the task (Spring's {@link DataSourceUtils}), so IBM's INSERT runs in the same unit of work as the rest of the
 * program: on the case's schema, committed or backed out with it. The connection it returns ignores
 * {@code close()}, as the transaction owns it; IBM's code never closes it anyway.
 */
public final class EndpointUrlDriver implements Driver {
    static final String URL = "endpoint_url";
    private static volatile DataSource dataSource;

    static synchronized void register(DataSource db2) throws SQLException {
        dataSource = db2;
        for (java.util.Enumeration<Driver> e = DriverManager.getDrivers(); e.hasMoreElements(); ) {
            if (e.nextElement() instanceof EndpointUrlDriver) {
                return;
            }
        }
        DriverManager.registerDriver(new EndpointUrlDriver());
    }

    @Override
    public boolean acceptsURL(String url) {
        return URL.equals(url);
    }

    @Override
    public Connection connect(String url, Properties info) throws SQLException {
        if (!acceptsURL(url)) {
            return null;  // DriverManager's contract: not this driver's URL
        }
        if (dataSource == null) {
            throw new SQLException("IBM WCA4Z adapter: no Db2 data source bound for " + URL);
        }
        Connection held = DataSourceUtils.getConnection(dataSource);
        InvocationHandler keepOpen = (proxy, method, args) -> {
            if ("close".equals(method.getName()) && method.getParameterCount() == 0) {
                return null;  // the transaction owns the connection
            }
            try {
                return method.invoke(held, args);
            } catch (InvocationTargetException e) {
                throw e.getCause();
            }
        };
        return (Connection) Proxy.newProxyInstance(Connection.class.getClassLoader(),
                new Class<?>[] {Connection.class}, keepOpen);
    }

    @Override
    public DriverPropertyInfo[] getPropertyInfo(String url, Properties info) {
        return new DriverPropertyInfo[0];
    }

    @Override
    public int getMajorVersion() {
        return 1;
    }

    @Override
    public int getMinorVersion() {
        return 0;
    }

    @Override
    public boolean jdbcCompliant() {
        return false;
    }

    @Override
    public Logger getParentLogger() throws SQLFeatureNotSupportedException {
        throw new SQLFeatureNotSupportedException();
    }
}
