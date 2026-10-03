package com.gitgalaxy.modernized.ibmwca4z;

import java.sql.SQLException;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * IBM WCA4Z adapter: binds {@link EndpointUrlDriver} to the Db2 data source the harness's generated repositories
 * and its per-task transaction use (EquivalenceDb2Config's primary template).
 */
@Component
public class EndpointUrlBinding {
    public EndpointUrlBinding(NamedParameterJdbcTemplate db2Jdbc) throws SQLException {
        EndpointUrlDriver.register(db2Jdbc.getJdbcTemplate().getDataSource());
    }
}
